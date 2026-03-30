<?php
// test_sales_api.php - Direct test of sales API
require_once __DIR__ '/api/db_config.php';

echo "<h1>🔧 SALES API TEST</h1>";

// Check if sales table exists
try {
    $result = $pdo->query("SHOW TABLES LIKE 'sales'");
    if ($result->rowCount() > 0) {
        echo "✅ Sales table exists<br>";
    } else {
        echo "❌ Sales table missing!<br>";
    }
} catch(Exception $e) {
    echo "❌ Error: " . $e->getMessage() . "<br>";
}

// Check sales table structure
echo "<h2>Sales Table Structure:</h2>";
$columns = $pdo->query("DESCRIBE sales");
echo "<table border='1' cellpadding='5'>";
echo "<tr><th>Field</th><th>Type</th><th>Null</th></tr>";
while ($col = $columns->fetch()) {
    echo "<tr>";
    echo "<td>" . $col['Field'] . "</td>";
    echo "<td>" . $col['Type'] . "</td>";
    echo "<td>" . $col['Null'] . "</td>";
    echo "</tr>";
}
echo "</table>";

// Check users (for created_by foreign key)
echo "<h2>Users in Database:</h2>";
$users = $pdo->query("SELECT id, username, role FROM users");
if ($users->rowCount() > 0) {
    echo "<table border='1' cellpadding='5'>";
    echo "<tr><th>ID</th><th>Username</th><th>Role</th></tr>";
    while ($user = $users->fetch()) {
        echo "<tr>";
        echo "<td>" . $user['id'] . "</td>";
        echo "<td>" . $user['username'] . "</td>";
        echo "<td>" . $user['role'] . "</td>";
        echo "</tr>";
    }
    echo "</table>";
} else {
    echo "<p style='color:red'>❌ No users found! Creating default user...</p>";
    $pdo->exec("INSERT INTO users (username, email, password_hash, full_name, role) VALUES ('admin', 'admin@example.com', 'temp', 'Admin', 'admin')");
    echo "<p style='color:green'>✅ Default user created!</p>";
}

// Test direct insert
echo "<h2>Test Direct Sale Insert:</h2>";
try {
    $pdo->beginTransaction();
    
    // Get a user ID
    $user = $pdo->query("SELECT id FROM users LIMIT 1")->fetch();
    $user_id = $user['id'];
    
    $invoice = 'TEST' . date('YmdHis');
    $stmt = $pdo->prepare("INSERT INTO sales (invoice_number, customer_name, grand_total, payment_method, created_by, created_at) VALUES (?, 'Test', 100, 'cash', ?, NOW())");
    $stmt->execute([$invoice, $user_id]);
    
    $sale_id = $pdo->lastInsertId();
    
    $pdo->commit();
    
    echo "<p style='color:green'>✅ Direct insert successful! Sale ID: $sale_id, Invoice: $invoice</p>";
    
} catch(Exception $e) {
    $pdo->rollBack();
    echo "<p style='color:red'>❌ Direct insert failed: " . $e->getMessage() . "</p>";
}

// Test the API endpoint directly
echo "<h2>Test API Endpoint:</h2>";
echo "<form method='post' action='api/sales/index.php' enctype='text/plain'>";
echo "<textarea name='json' rows='10' cols='50'>";
echo json_encode([
    'items' => [
        ['product_id' => 1, 'quantity' => 1, 'unit_price' => 50, 'total_price' => 50]
    ],
    'grand_total' => 50,
    'payment_method' => 'cash',
    'customer_name' => 'Test Customer'
], JSON_PRETTY_PRINT);
echo "</textarea><br>";
echo "<button type='submit'>Test API POST</button>";
echo "</form>";
?>