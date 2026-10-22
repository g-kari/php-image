<?php
/* Local, bounded API/roundtrip probe. No phpinfo, secrets or remote service login. */
function require_feature($ok, $what) { if (!$ok) { throw new RuntimeException($what); } }
function al2_feature_probe($series, $sapi) {
    require_feature(in_array($series,['7.4','8.0','8.1'],true),'Unexpected series');
    require_feature(PHP_SAPI===$sapi,'Wrong SAPI');
    $loaded=array_map('strtolower',get_loaded_extensions());
    $expected=['bcmath','bz2','calendar','ctype','curl','dba','dom','enchant','exif','fileinfo',
      'ftp','gd','gettext','gmp','iconv','intl','ldap','mbstring','mysqli','mysqlnd','odbc',
      'pdo','pdo_mysql','pdo_odbc','pdo_pgsql','pdo_sqlite','pgsql','phar','posix','pspell',
      'shmop','simplexml','snmp','soap','sockets','sodium','sqlite3','sysvmsg','sysvsem',
      'sysvshm','tokenizer','xml','xmlreader','xmlwriter','xsl','zip','json'];
    if ($series==='7.4') { $expected[]='xmlrpc'; }
    if (!in_array($sapi,['phpdbg','embed'],true)) { $expected[]='zend opcache'; }
    require_feature(!array_diff($expected,$loaded),'Missing baseline modules: '.implode(',',array_diff($expected,$loaded)));
    $cli=in_array($sapi,['cli','phpdbg','cgi-fcgi'],true);
    require_feature(function_exists('pcntl_fork')===$cli,'PCNTL SAPI isolation');
    require_feature(extension_loaded('readline')===$cli,'Readline SAPI isolation');
    require_feature(function_exists('mhash') && strlen(mhash(MHASH_SHA256,'test'))===32,'mhash API');
    require_feature(bcadd('1','2')==='3' && bzdecompress(bzcompress('local'))==='local','BCMath/bz2');
    require_feature(cal_days_in_month(CAL_GREGORIAN,2,2024)===29,'Calendar');
    require_feature(gmp_strval(gmp_add('20','22'))==='42','GMP');
    require_feature(mb_strlen('日本語','UTF-8')===3 && mb_ereg('^a+$','aaa')!==false,'mbstring/mbregex');
    require_feature(Normalizer::normalize("e\xCC\x81",Normalizer::FORM_C)==="\xC3\xA9",'ICU normalization');
    $gd=gd_info();
    foreach (['JPEG Support','FreeType Support','WebP Support'] as $format) {
        require_feature(!empty($gd[$format]),'GD '.$format);
    }
    $image=imagecreatetruecolor(2,2);
    ob_start();require_feature(imagepng($image),'GD PNG encode');$png=ob_get_clean();
    $decoded=imagecreatefromstring($png);
    require_feature($decoded!==false && imagesx($decoded)===2,'GD decode');
    imagedestroy($decoded);imagedestroy($image);
    $dir=sys_get_temp_dir().'/php-ci-'.bin2hex(random_bytes(8));
    require_feature(mkdir($dir,0700),'Private fixture directory');
    try {
        file_put_contents($dir.'/image.png',$png);
        require_feature(exif_imagetype($dir.'/image.png')===IMAGETYPE_PNG,'EXIF');
        $zip=new ZipArchive;
        require_feature($zip->open($dir.'/fixture.zip',ZipArchive::CREATE)===true,'ZIP create');
        require_feature($zip->addFromString('fixture.txt','local') && $zip->close(),'ZIP write');
        require_feature($zip->open($dir.'/fixture.zip')===true && $zip->getFromName('fixture.txt')==='local','ZIP read');
        $zip->close();
        $handlers=dba_handlers();
        foreach (['db4','tcadb'] as $handler) {
            require_feature(in_array($handler,$handlers,true),'DBA '.$handler);
            $db=dba_open($dir.'/db-'.$handler.($handler==='tcadb'?'.tch':'.db'),'n',$handler);
            require_feature($db!==false && dba_insert('key','value',$db) && dba_fetch('key',$db)==='value','DBA roundtrip');
            dba_close($db);
        }
        $pdo=new PDO('sqlite::memory:');
        require_feature($pdo->query('SELECT 42')->fetchColumn()==42,'PDO SQLite');
        $drivers=PDO::getAvailableDrivers();
        foreach (['mysql','pgsql','odbc','sqlite'] as $driver) {
            require_feature(in_array($driver,$drivers,true),'PDO '.$driver);
        }
        require_feature(function_exists('ldap_sasl_bind') && function_exists('pg_connect') && function_exists('odbc_connect'),'Client API registration');
        require_feature(is_int(snmp_get_valueretrieval()),'SNMP local API');
        $broker=enchant_broker_init();
        require_feature($broker!==false && is_array(enchant_broker_list_dicts($broker)),'Enchant broker');
        enchant_broker_free($broker);
        require_feature(function_exists('pspell_new') && function_exists('ftp_ssl_connect'),'Pspell/FTP TLS API');
        $soap=new SoapServer(null,['uri'=>'urn:local']);
        require_feature($soap instanceof SoapServer,'SOAP constructor');
        $xml=new DOMDocument;$xml->loadXML('<root>ok</root>',LIBXML_NONET);
        $sheet=new DOMDocument;
        $sheet->loadXML('<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"><xsl:template match="/"><out><xsl:value-of select="root"/></out></xsl:template></xsl:stylesheet>',LIBXML_NONET);
        $xsl=new XSLTProcessor;
        $xsl->setSecurityPrefs(XSL_SECPREF_READ_FILE|XSL_SECPREF_WRITE_FILE|XSL_SECPREF_CREATE_DIRECTORY|XSL_SECPREF_READ_NETWORK|XSL_SECPREF_WRITE_NETWORK);
        require_feature($xsl->importStylesheet($sheet) && strpos($xsl->transformToXML($xml),'<out>ok</out>')!==false,'XSL local transform');
        $key=random_bytes(SODIUM_CRYPTO_SECRETBOX_KEYBYTES);$nonce=random_bytes(SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        require_feature(sodium_crypto_secretbox_open(sodium_crypto_secretbox('local',$nonce,$key),$nonce,$key)==='local','Sodium roundtrip');
        $arrays=[[],['one'=>1],['nested'=>['value'=>2]],$_GET,$_POST,$_COOKIE];
        foreach ($arrays as $array) {
            require_feature(unserialize(serialize($array))===$array,'Array serialization');
            require_feature(array_replace([], $array)===$array,'Array merge');
        }
    } finally {
        foreach (glob($dir.'/*') as $file) { unlink($file); }rmdir($dir);
    }
    sort($loaded);
    $functions=get_defined_functions()['internal'];sort($functions);
    $constants=[];$resourceConstants=[];
    foreach (get_defined_constants() as $name=>$value) {
        if (is_resource($value)) { $resourceConstants[]=$name;continue; }
        $type=gettype($value);
        if (is_float($value) && (is_infinite($value) || is_nan($value))) { $value=(string)$value; }
        $constants[$name]=['type'=>$type,'value'=>$value];
    }
    ksort($constants);sort($resourceConstants);
    $classes=[];
    foreach (array_merge(get_declared_classes(),get_declared_interfaces()) as $name) {
        $reflection=new ReflectionClass($name);
        if (!$reflection->isInternal()) { continue; }
        $methods=[];
        foreach ($reflection->getMethods() as $method) { $methods[]=$method->getName(); }
        sort($methods);
        $classConstants=[];
        foreach ($reflection->getConstants() as $key=>$value) {
            $type=gettype($value);
            if (is_float($value) && (is_infinite($value) || is_nan($value))) { $value=(string)$value; }
            if (is_resource($value) || is_object($value)) { throw new RuntimeException('Unclassified internal class constant representation'); }
            $classConstants[$key]=['type'=>$type,'value'=>$value];
        }
        ksort($classConstants);
        $classes[$name]=['methods'=>$methods,'constants'=>$classConstants,'interface'=>$reflection->isInterface()];
    }
    ksort($classes);
    return ['series'=>$series,'sapi'=>PHP_SAPI,'version'=>PHP_VERSION,'zts'=>(bool)PHP_ZTS,
      'modules'=>$loaded,'internal_function_names'=>$functions,'internal_class_api'=>$classes,'defined_constants'=>$constants,'resource_constant_names'=>$resourceConstants,'gd'=>$gd,'dba_handlers'=>$handlers,'pdo_drivers'=>$drivers,
      'timezone_database'=>timezone_version_get(),'local_features'=>'passed',
      'limits'=>['Local APIs/roundtrips only, not database/LDAP/SNMP/FTP service interoperability.',
      'Named zts binary is recorded by actual PHP_ZTS, not assumed thread-safe.']];
}
