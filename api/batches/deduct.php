<?php
// api/batches/deduct.php - COMPLETE FIXED VERSION with barcode_scans
require_once __DIR__ . '/../../db_config.php';

header('Content-Type: application/json');

// Enable error reporting for debugging
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Only accept POST requests
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'error' => 'Method not allowed']);
    exit;
}

// Get POST data
$input = file_get_contents('php://input');
$data = json_decode($input, true);

$batch_id = $data['batch_id'] ?? 0;
$quantity = $data['quantity'] ?? 0;
$product_id = $data['product_id'] ?? 0;

if (!$batch_id || !$quantity || !$product_id) {
    echo json_encode([
        'success' => false, 
        'error' => 'Missing required fields',
        'received' => $data
    ]);
    exit;
}

try {
    $pdo->beginTransaction();
    
    // Get current batch
    $stmt = $pdo->prepare("SELECT remaining_quantity, batch_number FROM batches WHERE id = ? FOR UPDATE");
    $stmt->execute([$batch_id]);
    $batch = $stmt->fetch();
    
    if (!$batch) {
        throw new Exception('Batch not found');
    }
    
    if ($batch['remaining_quantity'] < $quantity) {
        throw new Exception('Insufficient stock in batch');
    }
    
    $new_quantity = $batch['remaining_quantity'] - $quantity;
    
    // Update batch quantity
    $updateStmt = $pdo->prepare("UPDATE batches SET remaining_quantity = ?, updated_at = NOW() WHERE id = ?");
    $updateStmt->execute([$new_quantity, $batch_id]);
    
    // Update batch status
    $statusStmt = $pdo->prepare("
        UPDATE batches 
        SET status = CASE 
            WHEN remaining_quantity = 0 THEN 'sold_out'
            WHEN remaining_quantity <= 10 THEN 'low_stock'
            WHEN expiry_date <= DATE_ADD(NOW(), INTERVAL 7 DAY) THEN 'expiring_soon'
            ELSE 'in_stock'
        END
        WHERE id = ?
    ");
    $statusStmt->execute([$batch_id]);
    
    // ✅ FIXED: Get product barcode for the scan log
    $productStmt = $pdo->prepare("SELECT barcode, product_name FROM products WHERE id = ?");
    $productStmt->execute([$product_id]);
    $product = $productStmt->fetch();
    
    if (!$product) {
        throw new Exception('Product not found');
    }
    
    // ✅ FIXED: Insert into barcode_scans table with ALL required fields
    $logStmt = $pdo->prepare("
        INSERT INTO barcode_scans (
            barcode, 
            product_id, 
            batch_id, 
            scan_type, 
            scanned_by, 
            is_successful, 
            scan_time,
            created_at
        ) VALUES (
            :barcode, 
            :product_id, 
            :batch_id, 
            'selling', 
            :scanned_by, 
            1, 
            NOW(),
            NOW()
        )
    ");
    
    // Get current user ID from session or default to 1
    $userId = $_SESSION['user_id'] ?? 1;
    
    $logStmt->execute([
        'barcode' => $product['barcode'],
        'product_id' => $product_id,
        'batch_id' => $batch_id,
        'scanned_by' => $userId
    ]);
    
    $pdo->commit();
    
    echo json_encode([
        'success' => true,
        'deducted' => $quantity,
        'remaining' => $new_quantity,
        'batch' => $batch['batch_number'],
        'product' => $product['product_name'],
        'barcode' => $product['barcode'],
        'message' => 'Stock deducted and scan logged successfully'
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