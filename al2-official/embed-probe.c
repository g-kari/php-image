#include <php.h>
#include <sapi/embed/php_embed.h>
int main(int argc,char **argv) {
 volatile int result=FAILURE;
 if (php_embed_init(argc,argv)==FAILURE) { return 1; }
 zend_first_try {
   result=zend_eval_string("require '/work/al2-official/probe-entry.php';",NULL,"bounded embedded probe");
 } zend_catch {
   result=FAILURE;
 } zend_end_try();
 php_embed_shutdown();
 return result==SUCCESS?0:1;
}
