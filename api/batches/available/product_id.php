<?php
// api/batches/available/product_id.php - DYNAMIC version
require_once __DIR__ . '/../../../db_config.php';

header('Content-Type: application/json');

// Get product_id from query parameter
$product_id = $_GET['id'] ?? 0;

if ($product_id == 0) {
    http_response_code(400);
    echo json_encode(['error' => 'Product ID parameter required']);
    exit;
}

try {
    $stmt = $pdo->prepare("
        SELECT id, batch_number, remaining_quantity, expiry_date, status
        FROM batches 
        WHERE product_id = :product_id 
        AND remaining_quantity > 0 
        AND is_active = 1
        AND status != 'expired'
        ORDER BY expiry_date ASC
    ");
    $stmt->execute(['product_id' => $product_id]);
    $batches = $stmt->fetchAll();
    
    echo json_encode($batches);
    
} catch(Exception $e) {
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage()]);
}
?>