from .. import toolchain_gcc
from wxPopen import ProcessLogger

class Xenomai_target(toolchain_gcc):
    extension = ".so"
    def getXenoConfig(self, flagsname):
        """ Get xeno-config from target parameters """
        xeno_config=self.PluginsRootInstance.GetTarget().getcontent()["value"].getXenoConfig()
        if xeno_config:
            status, result, err_result = ProcessLogger(self.PluginsRootInstance.logger,
                                                       xeno_config + " --skin=native --"+flagsname,
                                                       no_stdout=True).spin()
            if status:
                self.PluginsRootInstance.logger.write_error(_("Unable to get Xenomai's %s \n")%flagsname)
            return [result.strip()]
        return []
    
    def getBuilderLDFLAGS(self):
        xeno_ldflags = self.getXenoConfig("ldflags")
        return toolchain_gcc.getBuilderLDFLAGS(self) + xeno_ldlags + ["-shared", "-lnative"]

    def getBuilderCFLAGS(self):
        xeno_cflags = self.getXenoConfig("cflags")
        return toolchain_gcc.getBuilderCFLAGS(self) + xeno_cflags
        
