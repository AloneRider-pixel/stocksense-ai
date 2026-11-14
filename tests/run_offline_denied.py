"""Run local selected tests with inherited kernel denial of Internet sockets.

No runtime/application changes. AF_INET and AF_INET6 socket creation denied,
including native clients and child processes. Unix sockets remain available.
"""
import ctypes,errno,os,sys
lib=ctypes.CDLL('libseccomp.so.2',use_errno=True)
lib.seccomp_init.argtypes=[ctypes.c_uint32];lib.seccomp_init.restype=ctypes.c_void_p
lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
class Compare(ctypes.Structure):_fields_=[('arg',ctypes.c_uint),('op',ctypes.c_uint),('a',ctypes.c_uint64),('b',ctypes.c_uint64)]
lib.seccomp_rule_add_array.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint,ctypes.POINTER(Compare)]
lib.seccomp_load.argtypes=[ctypes.c_void_p]
ctx=lib.seccomp_init(0x7fff0000)
assert ctx
for domain in (2,10):
 rule=Compare(0,4,domain,0) # SCMP_CMP_EQ
 assert lib.seccomp_rule_add_array(ctx,0x50000|errno.EPERM,lib.seccomp_syscall_resolve_name(b'socket'),1,ctypes.byref(rule))==0
assert lib.seccomp_load(ctx)==0
import socket,subprocess
for family in (socket.AF_INET,socket.AF_INET6):
 try:socket.socket(family);raise AssertionError('denial not active')
 except PermissionError:pass
probe=subprocess.run([sys.executable,'-c','import socket;socket.socket(socket.AF_INET)'],capture_output=True,text=True)
assert probe.returncode!=0 and 'PermissionError' in probe.stderr
print('Kernel AF_INET/AF_INET6 denial verified in parent and child',flush=True)
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
