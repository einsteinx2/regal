#!/usr/bin/python -B

from string import Template, upper, replace

from ApiUtil import outputCode
from ApiUtil import typeIsVoid

from ApiCodeGen import *

from RegalDispatchShared import dispatchSourceTemplate
#from RegalDispatchLog import apiDispatchFuncInitCode
from RegalDispatchEmu import dispatchSourceTemplate
from RegalContextInfo import cond

##############################################################################################

def apiDispatchTableDefineCode(apis, args, apiNames, structName):
  code = '''
  struct %s
  {
    inline void setFunction(const size_t offset, void *func)
    {
      RegalAssert((offset*sizeof(void *))<sizeof(*this));
      ((void **)(this))[offset] = func;
    }
'''%(structName)

  for api in apis:

    if not api.name in apiNames:
      continue

    code += '\n'
    if api.name in cond:
      code += '#if %s\n' % cond[api.name]

    categoryPrev = None

    for function in api.functions:

      if getattr(function,'regalOnly',False)==True:
        continue

      name   = function.name
      params = paramsDefaultCode(function.parameters, True)
      rType  = typeCode(function.ret.type)
      category  = getattr(function, 'category', None)
      version   = getattr(function, 'version', None)

      if category:
        category = category.replace('_DEPRECATED', '')
      elif version:
        category = version.replace('.', '_')
        category = 'GL_VERSION_' + category

      # Close prev if block.
      if categoryPrev and not (category == categoryPrev):
        code += '\n'

      # Begin new if block.
      if category and not (category == categoryPrev):
        code += '    // %s\n\n' % category

      #code += '    %s(REGAL_CALL *%s)(%s);\n' % (rType, name, params)
      code += '    PFN%sPROC %s;\n' % (name.upper(), name)

      categoryPrev = category

    if api.name in cond:
      code += '#endif // %s\n' % cond[api.name]
    code += '\n'


  # Close pending if block.
  if categoryPrev:
    code += '\n'

  code += '  };\n'
  return code

dispatchHeaderTemplate = Template( '''${AUTOGENERATED}
${LICENSE}

#ifndef __${HEADER_NAME}_H__
#define __${HEADER_NAME}_H__

#include "RegalUtil.h"

REGAL_GLOBAL_BEGIN

#include <vector>
#include <GL/Regal.h>

REGAL_GLOBAL_END

REGAL_NAMESPACE_BEGIN

namespace Dispatch
{
${API_GLOBAL_DISPATCH_TABLE_DEFINE}

${API_DISPATCH_TABLE_DEFINE}
}
extern Dispatch::Global dispatchGlobal;

REGAL_NAMESPACE_END

#endif // __${HEADER_NAME}_H__
''')

def generateDispatchHeader(apis, args):

  substitute = {}

  substitute['LICENSE']         = args.license
  substitute['AUTOGENERATED']   = args.generated
  substitute['COPYRIGHT']       = args.copyright

  substitute['HEADER_NAME'] = 'REGAL_DISPATCH'
  substitute['API_GLOBAL_DISPATCH_TABLE_DEFINE'] = apiDispatchTableDefineCode(apis,args,['wgl','glx','cgl','egl'],'Global')
  substitute['API_DISPATCH_TABLE_DEFINE']        = apiDispatchTableDefineCode(apis,args,['gl'],'GL')

  outputCode( '%s/RegalDispatch.h' % args.srcdir, dispatchHeaderTemplate.substitute(substitute))
