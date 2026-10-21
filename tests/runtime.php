<?php
$profile = $argv[1] ?? '';
function require_check($ok, $message) { if (!$ok) { fwrite(STDERR, $message . PHP_EOL); exit(1); } }
require_check(in_array($profile, ['docker', 'al2'], true), 'unknown profile');
require_check(strlen(random_bytes(16)) === 16, 'random_bytes');
require_check(openssl_digest('sample', 'sha256') === hash('sha256', 'sample'), 'openssl_digest');
require_check(isset(curl_version()['version']), 'curl_version');
$db = new PDO('sqlite::memory:');
require_check((int)$db->query('SELECT 1')->fetchColumn() === 1, 'PDO SQLite');
require_check(opcache_compile_file(__DIR__ . '/request.php'), 'opcache_compile_file');
require_check(opcache_is_script_cached(__DIR__ . '/request.php'), 'opcache cache read');
if ($profile === 'docker') {
    require_check(mb_strlen('日本', 'UTF-8') === 2, 'mbstring');
    require_check(strlen(sodium_crypto_generichash('sample')) === 32, 'sodium');
} else {
    require_check(bcadd('1', '2') === '3', 'bcmath');
    require_check(function_exists('mysqli_init'), 'mysqli');
}
echo json_encode(['profile' => $profile, 'version' => PHP_VERSION, 'openssl' => OPENSSL_VERSION_TEXT, 'curl_ssl' => curl_version()['ssl_version'], 'checks' => 'passed']), PHP_EOL;
