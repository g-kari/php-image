<?php
require __DIR__.'/feature-probe.php';
require __DIR__.'/pecl-probe.php';
$series=$_GET['series'] ?? ($argv[1] ?? '');
require_feature(in_array($series,['7.4','8.0','8.1'],true),'Unexpected series');
$mode=$_GET['mode'] ?? 'features';
if ($mode==='oom') {
    ini_set('memory_limit','16M');
    register_shutdown_function(function () { echo 'CI-SHUTDOWN-MARKER'; });
    $chunks=[];while(true){$chunks[]=str_repeat('x',1048576);}
}
header('Content-Type: application/json');
if ($mode==='request') {
    session_save_path('/tmp');
    session_start();
    $_SESSION['counter']=($_SESSION['counter']??0)+1;
    $files=[];
    foreach ($_FILES as $name=>$file) {
        $files[$name]=['error'=>$file['error'],'size'=>$file['size'],
                       'uploaded'=>is_uploaded_file($file['tmp_name'])];
    }
    echo json_encode(['ok'=>true,'pid'=>getmypid(),'counter'=>$_SESSION['counter'],
      'progress'=>$_SESSION['upload_progress_ci']??null,'files'=>$files,'post'=>$_POST,
      'multipart_limit'=>ini_get('max_multipart_body_parts'),
      'opcache_loaded'=>extension_loaded('Zend OPcache'),
      'opcache_cached'=>function_exists('opcache_is_script_cached') && opcache_is_script_cached(__FILE__)]);
} else {
    $sapi=PHP_SAPI;
    echo json_encode(['features'=>al2_feature_probe($series,$sapi),'pecl'=>test_vendor_pecl($series)]);
}
echo "\n";
