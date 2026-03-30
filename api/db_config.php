<?php
// api/db_config.php - Unified database connection for PHP
$host = 'localhost';
$dbname = 'profit_recovery_erp_unified';  // ← UNIFIED database name
$username = 'root';
$password = '';  // ← Your MySQL password

try {
    $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8mb4", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    
    // Start session for user tracking
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
    
    // For testing, set a default user (in production, this comes from Flask login)
    if (!isset($_SESSION['user_id'])) {
        // Get sales user from database
        $stmt = $pdo->query("SELECT id FROM users WHERE role = 'sales_staff' LIMIT 1");
        $user = $stmt->fetch();
        $_SESSION['user_id'] = $user ? $user['id'] : 1;
    }
} catch(PDOException $e) {
    header('Content-Type: application/json');
    http_response_code(500);
    echo json_encode(['error' => 'Database connection failed: ' . $e->getMessage()]);
    exit;
}
?>