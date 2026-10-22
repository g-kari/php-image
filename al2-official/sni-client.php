<?php
$ca=$argv[1];$expected='4a524f3617e41bcca1370ed9e89c9a7a83c28f0f342c490296d362869bdf1da8';
$results=[];
foreach (['openssl.php.net','wrong-peer.invalid','openssl.php.net'] as $index=>$name) {
    $context=stream_context_create(['ssl'=>['cafile'=>$ca,'verify_peer'=>true,'verify_peer_name'=>true,
      'allow_self_signed'=>false,'peer_name'=>$name,'SNI_enabled'=>true,'capture_peer_cert'=>true]]);
    $warnings=[];
    set_error_handler(function($n,$s)use(&$warnings){$warnings[]=$s;return true;});
    try { $socket=stream_socket_client('tls://127.0.0.1:19443',$errno,$error,5,STREAM_CLIENT_CONNECT,$context); }
    finally { restore_error_handler(); }
    if ($index===1) {
        if ($socket) { fclose($socket);throw new RuntimeException('Wrong peer name accepted'); }
        if (!preg_match('/did not match|does not match|hostname mismatch/i',implode("\n",$warnings))) {
            throw new RuntimeException('Negative TLS error is not a verified hostname rejection: '.implode(';',$warnings));
        }
        $results[]=['peer'=>$name,'hostname_rejected'=>true,'warnings'=>$warnings];
    } else {
        if (!$socket) { throw new RuntimeException('Positive strict local TLS failed: '.$errno.' '.$error.' '.implode(';',$warnings)); }
        $params=stream_context_get_params($socket);
        $certificate=$params['options']['ssl']['peer_certificate'];
        $fingerprint=openssl_x509_fingerprint($certificate,'sha256');
        if ($fingerprint!==$expected) { throw new RuntimeException('Unexpected fixture certificate'); }
        stream_set_timeout($socket,5);
        $response=stream_get_contents($socket);$metadata=stream_get_meta_data($socket);fclose($socket);
        if ($metadata['timed_out'] || strpos($response,"HTTP/1.0 200 OK")!==0) {
            throw new RuntimeException('Local TLS fixture response failed');
        }
        $results[]=['peer'=>$name,'certificate_sha256'=>$fingerprint,'strict_peer_and_hostname'=>true];
    }
}
echo json_encode(['positive_negative_positive'=>$results,'scope'=>'One existing public test identity; no multi-host SNI selection claim.']),"\n";
