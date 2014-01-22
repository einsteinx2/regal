#!/usr/bin/python -B

from string import Template, upper, replace

from ApiUtil import outputCode
from ApiUtil import typeIsVoid

from ApiCodeGen import *

from RegalContext     import emu
from RegalContextInfo import cond

from Emu       import emuFindEntry, emuCodeGen, emuGetOriginateList, emuGetInterceptList

##############################################################################################

emuProcsHeaderTemplate = Template('''${AUTOGENERATED}
${LICENSE}

#ifndef ${HEADER_NAME}
#define ${HEADER_NAME}

#include "RegalUtil.h"

${IFDEF}REGAL_GLOBAL_BEGIN

#include "RegalPrivate.h"
#include "RegalContext.h"
#include "RegalDispatch.h"
${LOCAL_INCLUDE}

REGAL_GLOBAL_END

REGAL_NAMESPACE_BEGIN

${LOCAL_CODE}

REGAL_NAMESPACE_END

${ENDIF}
#endif // ${HEADER_NAME}
''')

emuProcsSourceTemplate = Template('''${AUTOGENERATED}
${LICENSE}

#include "RegalUtil.h"

${IFDEF}
REGAL_GLOBAL_BEGIN

#include "RegalPrivate.h"
#include "RegalContext.h"
#include "RegalDispatch.h"
${LOCAL_INCLUDE}

REGAL_GLOBAL_END

REGAL_NAMESPACE_BEGIN

${LOCAL_CODE}

REGAL_NAMESPACE_END

${ENDIF}
''')

##############################################################################################

def apiEmuProcsHeaderCode( e, apis, orig ):
  code = ''

  code +=     'void EmuProcsIntercept%s( Dispatch::GL & dt );\n\n' % e['suffix']

  o = emuGetOriginateList( e['formulae'], apis )
  for f in orig:
    if f not in o:
      o.append( f )
  o = sorted( o )

  if len(o) == 0:
    return code

  code +=     'struct EmuProcsOriginate%s {\n' % e['suffix']
  code +=     '\n'
  code +=     '  EmuProcsOriginate%s() {\n' % e['suffix']
  code +=     '    memset(this, 0, sizeof( *this ) );\n'
  code +=     '  }\n'
  code +=     '\n'
  for oe in o:
    code +=   '  REGAL%sPROC %s;\n' % ( oe.upper(), oe )
  code +=     '\n'
  code +=     '  void Initialize( Dispatch::GL & dt ) {\n'
  for oe in o:
    code +=   '    %s = dt.%s;\n' % ( oe, oe )
  code +=     '  }\n'
  code +=     '};\n\n'

  return code

def callAndReturn( e, function ):
  code = ''
  
  name   = function.name
  callParams = paramsNameCode(function.parameters)
  rType  = typeCode(function.ret.type)

  if not typeIsVoid(rType):
    code += 'return '
  if len(callParams) == 0:
    callParams = "_context"
  else:
    callParams = "_context, %s" % callParams
  code += 'orig.%s( %s );\n' % ( name, callParams )
  
  return code

def apiEmuProcsSourceCode( e, apis, orig ):
  code = ''

  intercept = []
  ore = re.compile( "orig.gl[A-Za-z0-9_]+" );

  for api in apis:

    code += '\n'

    for function in sorted( api.functions, key = lambda function: function.name):
      if not function.needsContext:
        continue
      if getattr(function,'regalOnly',False)==True:
        continue

      name   = function.name
      params = paramsDefaultCode(function.parameters, True, paramsPrefix = "RegalContext *_context")
      callParams = paramsNameCode(function.parameters)
      rType  = typeCode(function.ret.type)
      category  = getattr(function, 'category', None)
      version   = getattr(function, 'version', None)

      emue = emuFindEntry( function, e['formulae'], e['member'] )

      if not emue:
        continue

      intercept.append( name )

      code +=      '\nstatic %sREGAL_CALL %s%s(%s) \n{\n' % (rType, 'emuProcIntercept%s_' % e['suffix'], name, params)
      code +=      '  RegalAssert(_context);\n'

      body =       ''
      if emue != None and 'prefix' in emue and len(emue['prefix']):
        body +=    '  // prefix\n'
        body += listToString( indent( emue['prefix'], '  ' ) )
        if body.find("return") > 0:
          raise Exception("Cannot early return in prefix clause. - %s %s" % ( e['suffix'], name ) )

      elif emue != None and 'impl' in emue and len( emue['impl'] ):
        body +=    '  // impl\n'
        body += listToString( indent( emue['impl'], '  ' ) )
        if body.find("return") < 0:
          raise Exception("Must have at least one return in impl clause. - %s %s" % ( e['suffix'], name ) )


      body +=      '\n'
      body +=      '  ' + callAndReturn( e, function )
      body +=      '\n'
      body +=      '}\n'

      calls = ore.findall( body )
      if calls:
        for c in calls:
          c = c[5:]
          if c not in orig:
            orig.append( c )
        code +=      '  EmuProcsOriginate%s & orig = _context->%s->orig;\n' % ( e['suffix'], e['member'] )
      code +=      '\n'

      code += body

  code +=     'void EmuProcsIntercept%s( Dispatch::GL & dt ) {\n' % e['suffix']
  maxf = 0
  for f in intercept:
    maxf = max( maxf, len(f) )
  for f in sorted(intercept):
    spc = ' ' * ( maxf - len(f) )
    code +=     '  dt.%s%s = emuProcIntercept%s_%s;\n' % ( f, spc, e['suffix'], f )
  code +=     '}\n'
  return code


def generateEmuSource(apis, args):

  orig = {}
 
  for e in emu:
    if not e['formulae']:
      continue
    s = {}
    s['LICENSE']         = args.license
    s['AUTOGENERATED']   = args.generated
    s['COPYRIGHT']       = args.copyright
    origfuncs = orig[ e['suffix'] ] = []
    s['LOCAL_CODE']      = apiEmuProcsSourceCode( e, apis, origfuncs )
    s['LOCAL_INCLUDE']   = '#include "Regal%s.h"\n#include "RegalEmuProcs%s.h"\n' % (e['suffix'],e['suffix'])
    s['API_DISPATCH_FUNC_DEFINE'] = ''
    s['API_DISPATCH_FUNC_INIT'] = ''
    s['API_DISPATCH_GLOBAL_FUNC_INIT'] = ''
    s['IFDEF'] = '#if REGAL_EMULATION\n\n'
    s['ENDIF'] = '#endif // REGAL_EMULATION\n'

    outputCode( '%s/layer/%s/%sProcs.cpp' % (args.srcdir, e['member'], e['suffix']), emuProcsSourceTemplate.substitute(s))

  for e in emu:
    if not e['formulae']:
      continue
    s = {}
    s['LICENSE']         = args.license
    s['AUTOGENERATED']   = args.generated
    s['COPYRIGHT']       = args.copyright
    s['HEADER_NAME']   = 'REGAL_EMU_PROCS_%s_H' % e['suffix'].upper()
    origfuncs = orig[ e['suffix'] ]
    s['LOCAL_CODE']      =  apiEmuProcsHeaderCode( e, apis, origfuncs )
    s['LOCAL_INCLUDE']   = ''
    s['API_DISPATCH_FUNC_DEFINE'] = ''
    s['API_DISPATCH_FUNC_INIT'] = ''
    s['API_DISPATCH_GLOBAL_FUNC_INIT'] = ''
    s['IFDEF'] = '#if REGAL_EMULATION\n\n'
    s['ENDIF'] = '#endif // REGAL_EMULATION\n'

    outputCode( '%s/layer/%s/%sProcs.h' % (args.srcdir, e['member'], e['suffix']), emuProcsHeaderTemplate.substitute(s))

