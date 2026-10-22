#include <php.h>
#include <zend_globals.h>
#include <zend_compile.h>
#include <zend_execute.h>
#include <ext/pdo/php_pdo_driver.h>
#include <stddef.h>
#include <stdio.h>
#define SIZE(t) printf("sizeof.%s=%zu\n",#t,sizeof(t))
#define OFFSET(t,m) printf("offset.%s.%s=%zu\n",#t,#m,offsetof(t,m))
int main(void) {
 SIZE(zval); SIZE(zend_array); SIZE(zend_string); SIZE(zend_object); SIZE(zend_reference);
 SIZE(zend_execute_data); SIZE(zend_function); SIZE(zend_class_entry);
 SIZE(zend_compiler_globals); SIZE(zend_executor_globals);
 OFFSET(zend_compiler_globals,ast); OFFSET(zend_compiler_globals,ast_arena);
 OFFSET(zend_executor_globals,current_execute_data); OFFSET(zend_executor_globals,exception);
 OFFSET(zend_executor_globals,reserved);
 printf("php_api=%d\nzend_api=%d\npdo_driver_api=%d\n",PHP_API_VERSION,ZEND_MODULE_API_NO,PDO_DRIVER_API);
#ifdef ZTS
 printf("zts=1\n");
#else
 printf("zts=0\n");
#endif
 return 0;
}
