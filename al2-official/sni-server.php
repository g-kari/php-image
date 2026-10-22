<?php
/* A public, existing PHP upstream test key. Never suitable for a real service. */
$fixture=$argv[1];
$context=stream_context_create(['ssl'=>['local_cert'=>$fixture,
  'SNI_server_certs'=>['openssl.php.net'=>$fixture],'verify_peer'=>false]]);
$server=stream_socket_server('tls://127.0.0.1:19443',$errno,$error,STREAM_SERVER_BIND|STREAM_SERVER_LISTEN,$context);
if (!$server) { throw new RuntimeException('Local TLS fixture listener: '.$errno.' '.$error); }
file_put_contents('/tmp/ci-sni-ready','ready');
for ($i=0;$i<3;$i++) {
    $warnings=[];
    set_error_handler(function($n,$s)use(&$warnings){$warnings[]=$s;return true;});
    try { $client=stream_socket_accept($server,10); } finally { restore_error_handler(); }
    if ($client) { fwrite($client,"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok");fclose($client); }
    echo json_encode(['connection'=>$i,'accepted'=>(bool)$client,'warnings'=>$warnings]),"\n";
}
fclose($server);
