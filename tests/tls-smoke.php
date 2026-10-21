<?php
// One public origin; no credentials/cookies, redirects, CA changes or verify bypass.
$order = $argv[1] ?? '';
if (!in_array($order, ['curl-first', 'stream-first'], true)) { exit(2); }
function ensure_tls($ok, $why) { if (!$ok) { throw new RuntimeException($why); } }
function curl_head() {
    $h = curl_init('https://www.php.net/robots.txt');
    curl_setopt_array($h, [
        CURLOPT_NOBODY => true, CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => false, CURLOPT_MAXREDIRS => 0,
        CURLOPT_CONNECTTIMEOUT => 5, CURLOPT_TIMEOUT => 15,
        CURLOPT_SSL_VERIFYPEER => true, CURLOPT_SSL_VERIFYHOST => 2,
        CURLOPT_PROTOCOLS => CURLPROTO_HTTPS, CURLOPT_NETRC => CURL_NETRC_IGNORED,
    ]);
    $response = curl_exec($h);
    $status = (int)curl_getinfo($h, CURLINFO_HTTP_CODE);
    $verify = (int)curl_getinfo($h, CURLINFO_SSL_VERIFYRESULT);
    $error = curl_error($h);
    curl_close($h);
    ensure_tls($response !== false, 'curl TLS failed: ' . $error);
    ensure_tls($verify === 0 && $status >= 200 && $status < 400, 'curl certificate/status failure');
    return ['client' => 'curl', 'http_status' => $status, 'ssl_verify_result' => $verify,
        'ssl_backend' => curl_version()['ssl_version']];
}
function stream_head() {
    $context = stream_context_create(['ssl' => [
        'verify_peer' => true, 'verify_peer_name' => true,
        'peer_name' => 'www.php.net', 'allow_self_signed' => false,
        'SNI_enabled' => true, 'disable_compression' => true,
    ]]);
    $socket = stream_socket_client('tls://www.php.net:443', $errno, $errstr, 5, STREAM_CLIENT_CONNECT, $context);
    ensure_tls(is_resource($socket), 'OpenSSL stream TLS failed: ' . $errno . ' ' . $errstr);
    stream_set_timeout($socket, 15);
    $request = "HEAD /robots.txt HTTP/1.1\r\nHost: www.php.net\r\nConnection: close\r\n\r\n";
    ensure_tls(fwrite($socket, $request) === strlen($request), 'TLS stream request write failed');
    $line = fgets($socket, 2048);
    $meta = stream_get_meta_data($socket);
    fclose($socket);
    ensure_tls(!$meta['timed_out'] && is_string($line) && preg_match('~^HTTP/1\.[01] ([0-9]{3}) ~', $line, $match), 'TLS stream HTTP response failed');
    $status = (int)$match[1];
    ensure_tls($status >= 200 && $status < 400, 'TLS stream HTTP status failure');
    return ['client' => 'openssl-stream', 'http_status' => $status,
        'crypto' => $meta['crypto'] ?? null, 'openssl' => OPENSSL_VERSION_TEXT];
}
try {
    ensure_tls(openssl_digest('sample', 'sha256') === hash('sha256', 'sample'), 'initial OpenSSL digest');
    $results = $order === 'curl-first'
        ? [curl_head(), stream_head(), curl_head()]
        : [stream_head(), curl_head(), stream_head()];
    ensure_tls(openssl_digest('sample', 'sha256') === hash('sha256', 'sample'), 'post-TLS OpenSSL digest');
    ensure_tls(strlen(random_bytes(16)) === 16, 'post-TLS randomness');
    echo json_encode(['order' => $order, 'origin' => 'https://www.php.net/robots.txt',
        'strict_certificate_hostname_verification' => true, 'redirects_followed' => false,
        'results' => $results, 'checks' => 'passed']), PHP_EOL;
} catch (Throwable $e) {
    fwrite(STDERR, $e->getMessage() . PHP_EOL);
    exit(1);
}
