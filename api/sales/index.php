<?php
// api/sales/index.php - Handles both JSON and form data
require_once __DIR__ . '/../../db_config.php';

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'error' => 'Method not allowed']);
    exit;
}

// Get raw input
$input = file_get_contents('php://input');
error_log("Raw input: " . $input);

// Try to decode as JSON first
$data = json_decode($input, true);

// If JSON decode failed, try parsing as form data
if (!$data && strpos($input, 'json=') === 0) {
    // Remove 'json=' prefix and decode
    $jsonStr = substr($input, 5);
    $data = json_decode($jsonStr, true);
    error_log("Parsed as form data: " . print_r($data, true));
}

// If still no data, try $_POST
if (!$data && !empty($_POST)) {
    $data = $_POST;
    if (isset($data['json'])) {
        $data = json_decode($data['json'], true);
    }
}

// Check if we have valid data
if (!$data) {
    echo json_encode([
        'success' => false, 
        'error' => 'Invalid data format',
        'received' => $input
    ]);
    exit;
}

try {
    $pdo->beginTransaction();
    
    // Get valid user ID
    $userStmt = $pdo->query("SELECT id FROM users LIMIT 1");
    $user = $userStmt->fetch();
    
    if (!$user) {
        $pdo->exec("INSERT INTO users (username, email, password_hash, full_name, role) 
                    VALUES ('cashier', 'cashier@example.com', 'temp', 'Cashier', 'sales_staff')");
        $userId = $pdo->lastInsertId();
    } else {
        $userId = $user['id'];
    }
    
    // Calculate totals
    $subtotal = $data['subtotal'] ?? $data['grand_total'] ?? 0;
    $grand_total = $data['grand_total'] ?? $subtotal;
    
    // Generate invoice
    $invoice_number = 'INV' . date('Ymd') . rand(1000, 9999);
    
    // Insert sale
    $saleStmt = $pdo->prepare("
        INSERT INTO sales (
            invoice_number, customer_name, subtotal, grand_total, 
            payment_method, payment_status, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, NOW())
    ");
    
    $saleStmt->execute([
        $invoice_number,
        $data['customer_name'] ?? 'Walk-in Customer',
        $subtotal,
        $grand_total,
        $data['payment_method'] ?? 'cash',
        $data['payment_status'] ?? 'paid',
        $userId
    ]);
    
    $sale_id = $pdo->lastInsertId();
    
    // Insert items
    if (!empty($data['items']) && is_array($data['items'])) {
        $itemStmt = $pdo->prepare("
            INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?)
        ");
        
        foreach ($data['items'] as $item) {
            if (isset($item['product_id']) && $item['product_id'] > 0) {
                $itemStmt->execute([
                    $sale_id,
                    $item['product_id'],
                    $item['quantity'] ?? 1,
                    $item['unit_price'] ?? 0,
                    $item['total_price'] ?? ($item['unit_price'] * $item['quantity'])
                ]);
            }
        }
    }
    
    $pdo->commit();
    
    echo json_encode([
        'success' => true,
        'sale_id' => $sale_id,
        'invoice_number' => $invoice_number,
        'message' => 'Sale recorded successfully'
    ]);
    
} catch(Exception $e) {
    $pdo->rollBack();
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => $e->getMessage()
    ]);
}
?>