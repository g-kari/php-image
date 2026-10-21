<?php
if (isset($_GET['oom'])) {
    ini_set('memory_limit', '16M');
    register_shutdown_function(function () { echo 'SHUTDOWN-MUST-NOT-RUN'; });
    $a = []; while (true) { $a[] = str_repeat('x', 1048576); }
}
session_save_path('/tmp');
session_start();
$_SESSION['counter'] = ($_SESSION['counter'] ?? 0) + 1;
header('Content-Type: application/json');
echo json_encode(['ok' => true, 'pid' => getmypid(), 'version' => PHP_VERSION,
    'opcache' => extension_loaded('Zend OPcache'), 'counter' => $_SESSION['counter'],
    'files' => array_keys($_FILES), 'post' => $_POST]);
