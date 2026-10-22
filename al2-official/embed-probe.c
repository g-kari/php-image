#include <php.h>
#include <sapi/embed/php_embed.h>
int main(int argc,char **argv) {
 int result=FAILURE;
 PHP_EMBED_START_BLOCK(argc,argv)
   result=zend_eval_string("require '/work/al2-official/probe-entry.php';",NULL,"bounded embedded probe");
 PHP_EMBED_END_BLOCK()
 return result==SUCCESS?0:1;
}
