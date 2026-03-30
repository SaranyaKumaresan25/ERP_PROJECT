<?php
// api/products/barcode/{barcode}.php
// Example: /api/products/barcode/8901234567890

require_once __DIR__ '/../../../db_config.php';

// Get barcode from URL
$request_uri = $_SERVER['REQUEST_URI'];
$parts = explode('/barcode/', $request_uri);
$barcode = end($parts);
$barcode = preg_replace('/[^a-zA-Z0-9]/', '', $barcode); // Clean barcode

header('Content-Type: application/json');

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