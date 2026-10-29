"""Unicode ShellLinkW/IPersistFile adapter; no locale-dependent WScript.Save."""
import ctypes
import uuid


class ShellLink:
    def __enter__(self):
        self.api=ctypes.OleDLL('ole32')
        self.api.CoInitializeEx.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
        self.initialized=self.api.CoInitializeEx(None,2)>=0
        self.pointer=ctypes.c_void_p()
        self.api.CoCreateInstance.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
        self.api.CoCreateInstance(ctypes.byref(self.guid('00021401-0000-0000-C000-000000000046')),None,1,
            ctypes.byref(self.guid('000214F9-0000-0000-C000-000000000046')),ctypes.byref(self.pointer))
        self.persist=ctypes.c_void_p()
        self.call(self.pointer,0,[ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)],
                  ctypes.byref(self.guid('0000010b-0000-0000-C000-000000000046')),ctypes.byref(self.persist))
        return self

    @staticmethod
    def guid(value):return (ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID(value).bytes_le)

    @staticmethod
    def call(pointer,index,types,*args):
        table=ctypes.cast(pointer,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        result=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,*types)(table[index])(pointer,*args)
        if result<0:raise OSError('ShellLink HRESULT '+hex(result&0xffffffff))

    def __exit__(self,*_):
        if self.persist:self.call(self.persist,2,[])
        if self.pointer:self.call(self.pointer,2,[])
        if self.initialized:self.api.CoUninitialize()


def create(target,interpreter,arguments,directory,icon):
    with ShellLink() as link:
        for index,value in ((20,interpreter),(11,arguments),(9,directory),(7,'Codex Extension Catalogue')):
            link.call(link.pointer,index,[ctypes.c_wchar_p],str(value))
        link.call(link.pointer,17,[ctypes.c_wchar_p,ctypes.c_int],str(icon),0)
        link.call(link.persist,6,[ctypes.c_wchar_p,ctypes.c_int],str(target),1)


def inspect(target):
    with ShellLink() as link:
        link.call(link.persist,5,[ctypes.c_wchar_p,ctypes.c_ulong],str(target),0)
        path=ctypes.create_unicode_buffer(32768);args=ctypes.create_unicode_buffer(32768)
        link.call(link.pointer,3,[ctypes.c_wchar_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_ulong],path,len(path),None,0)
        link.call(link.pointer,10,[ctypes.c_wchar_p,ctypes.c_int],args,len(args))
        return {'target':path.value,'arguments':args.value}
