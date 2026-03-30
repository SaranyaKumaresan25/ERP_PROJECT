<?php
// api/products/barcode/barcode.php - DYNAMIC version
require_once __DIR__ . '/../../../db_config.php';

header('Content-Type: application/json');

// Get barcode from query parameter
$barcode = $_GET['code'] ?? '';

if (empty($barcode)) {
    http_response_code(400);
    echo json_encode(['error' => 'Barcode parameter required']);
    exit;
}

try {
    // Find product by barcode
    $stmt = $pdo->prepare("
        SELECT id, product_code, barcode, product_name, selling_price
        FROM products 
        WHERE barcode = :barcode OR product_code = :barcode
        LIMIT 1
    ");
    $stmt->execute(['barcode' => $barcode]);
    $product = $stmt->fetch();
    
    if ($product) {
        echo json_encode($product);
    } else {
        http_response_code(404);
        echo json_encode(['error' => 'Product not found']);
    }
    
} catch(Exception $e) {
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage()]);
}
?>