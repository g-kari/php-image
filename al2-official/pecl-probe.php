<?php
/* Local, bounded PECL compatibility checks. No service connections or credentials. */
function test_vendor_pecl($series) {
    $required = $series === '7.4' ? ['apcu','igbinary','imagick','mailparse','memcache','memcached','msgpack','oauth','redis','ssh2','uuid'] : ($series === '8.0' ? ['imagick'] : []);
    foreach ($required as $extension) {
        if (!extension_loaded($extension)) { throw new RuntimeException('Missing official PECL '.$extension); }
    }
    $sample = [[],['one'=>'value'],[0=>'zero','n'=>123,'nested'=>['unicode'=>'日本語']]];
    $sample[] = ['get'=>$_GET,'post'=>$_POST,'cookie'=>$_COOKIE];
    if ($series === '7.4') {
        foreach ($sample as $value) {
            if (igbinary_unserialize(igbinary_serialize($value)) !== $value) { throw new RuntimeException('igbinary roundtrip'); }
            if (msgpack_unpack(msgpack_pack($value)) !== $value) { throw new RuntimeException('msgpack roundtrip'); }
            $key = 'ci-'.getmypid().'-'.bin2hex(random_bytes(8));
            if (apcu_enabled() && !apcu_store($key,$value,10)) { throw new RuntimeException('APCu store'); }
            $ok = false;
            if (apcu_enabled()) { $got = apcu_fetch($key,$ok); apcu_delete($key); }
            if (apcu_enabled() && (!$ok || $got !== $value)) { throw new RuntimeException('APCu roundtrip'); }
        }
        $redis = new Redis;
        if (!$redis->setOption(Redis::OPT_SERIALIZER,Redis::SERIALIZER_IGBINARY)) { throw new RuntimeException('Redis igbinary registration'); }
        $memcached = new Memcached;
        if (!$memcached->setOption(Memcached::OPT_SERIALIZER,Memcached::SERIALIZER_IGBINARY)) { throw new RuntimeException('Memcached igbinary registration'); }
        if (!$memcached->setOption(Memcached::OPT_SERIALIZER,Memcached::SERIALIZER_MSGPACK)) { throw new RuntimeException('Memcached msgpack registration'); }
        $memcache = new Memcache;
        $message = mailparse_msg_create();
        mailparse_msg_parse($message,"From: fixture@example.invalid\r\nContent-Type: text/plain\r\n\r\nlocal\r\n");
        if (!mailparse_msg_get_structure($message)) { throw new RuntimeException('mailparse local MIME'); }
        mailparse_msg_free($message);
        $oauth = new OAuth('public-fixture','public-fixture-value');
        if (!function_exists('ssh2_connect')) { throw new RuntimeException('SSH2 registration'); }
        $uuid = uuid_create(UUID_TYPE_RANDOM);
        if (!uuid_is_valid($uuid)) { throw new RuntimeException('UUID generation'); }
    }
    if (in_array('imagick',$required,true)) {
        $image = new Imagick;
        $image->newImage(1,1,new ImagickPixel('red'),'png');
        $blob = $image->getImagesBlob();
        if (strlen($blob)<8 || substr($blob,0,8)!=="\x89PNG\r\n\x1a\n") { throw new RuntimeException('Imagick PNG'); }
        $image->clear(); $image->destroy();
    }
    return ['series'=>$series,'official_pecl_modules'=>$required,'apcu_runtime_enabled'=>function_exists('apcu_enabled')?apcu_enabled():null,'bounded_local_checks'=>'passed',
        'limits'=>['no Redis/Memcached/SSH server interoperability test','not an assertion every extension-specific vulnerability is covered']];
}
