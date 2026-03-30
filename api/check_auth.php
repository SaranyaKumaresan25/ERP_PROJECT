<?php
// api/check-auth.php - Check if user is authenticated
require_once __DIR__ . '/../db_config.php';  // Goes up one level

header('Content-Type: application/json');

// For demo purposes, always return authenticated
echo json_encode([
    'authenticated' => true,
    'user' => [
        'id' => $_SESSION['user_id'],
        'username' => 'cashier',
        'full_name' => 'Test Cashier'
    ]
]);
?>