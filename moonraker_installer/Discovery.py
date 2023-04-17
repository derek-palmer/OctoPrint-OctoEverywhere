import os

from .Util import Util
from .Logging import Logger
from .Context import Context


class ServiceFileConfigPathPair:
    def __init__(self, serviceFileName, moonrakerConfigPath) -> None:
        self.ServiceFileName = serviceFileName
        self.MoonrakerConfigFilePath = moonrakerConfigPath


# This class is used for the hardest part of the install, mapping the moonraker service instances to the moonraker config files.
# I wish this was easier, but it's quite hard because the service files don't exactly reference the moonraker.conf.
# On top of that, there's variations in how the config files are created for different Klipper based systems.
#
# TODO - One thing we could do is use systemctl status moonraker<id> and check the actual cmd line args. That will resolve all of the macros
# and we should be able to parse out the -d flag for the older klipper_config flags.
class Discovery:

    def FindTargetMoonrakerFiles(self, context:Context):
        Logger.Debug("Starting discovery.")

        # Print all of the file options, so we have them for debugging.
        # We always print these, so they show up in the log file.
        self._PrintDebugPaths(context)

        # If we were passed a valid moonraker config file and service name, we don't need to do anything else.
        if context.MoonrakerConfigFilePath is not None:
            if os.path.exists(context.MoonrakerConfigFilePath):
                if context.MoonrakerServiceFileName is not None and len(context.MoonrakerServiceFileName) > 0:
                    Logger.Info(f"Installer script was passed a valid Moonraker config and service name. [{context.MoonrakerServiceFileName}:{context.MoonrakerConfigFilePath}]")
                    return

        # If we are here, we either have no service file name but a config path, or neither.
        # To start, we will enumerate all moonraker service files we can find and their possible
        # moonraker config parings.
        # For details about why we need these, read the readme.py file in this module.
        pairList = self._FindAllServiceFilesAndPairings()

        # Ensure we found something.
        if pairList is None or len(pairList) == 0:
            raise Exception("No moonraker instances could be detected on this device.")

        # Now that we have list of all moonraker config and service file pairs, match the moonraker config passed in, if there is one.
        if context.MoonrakerConfigFilePath is not None:
            for p in pairList:
                if p.MoonrakerConfigFilePath == context.MoonrakerConfigFilePath:
                    # Update the context and return!
                    context.MoonrakerServiceFileName = p.ServiceFileName
                    Logger.Info(f"The given moonraker config was found with a service file pair. [{context.MoonrakerServiceFileName}:{context.MoonrakerConfigFilePath}]")
                    return
            Logger.Warn(f"Moonraker config path [{context.MoonrakerConfigFilePath}] was given, but no found pair matched it.")

        # If there is just one pair, always use it.
        if len(pairList) == 1 and context.DisableAutoMoonrakerInstanceSelection is False:
            # Update the context and return!
            context.MoonrakerConfigFilePath = pairList[0].MoonrakerConfigFilePath
            context.MoonrakerServiceFileName = pairList[0].ServiceFileName
            Logger.Info(f"Only one moonraker instance was found, so we are using it! [{context.MoonrakerServiceFileName}:{context.MoonrakerConfigFilePath}]")
            return

        # If there are many found, as the user which they 0want to use.
        Logger.Blank()
        Logger.Blank()
        Logger.Warn("Multiple Moonraker instances found.")
        Logger.Warn("An instance of OctoEverywhere must be installed for every Moonraker instance, so this installer must be ran for each instance individually.")
        Logger.Blank()
        # Print the config files found.
        count = 0
        for p in pairList:
            count += 1
            Logger.Info(F"  {str(count)} {p.ServiceFileName} [{p.MoonrakerConfigFilePath}]")
        Logger.Blank()

        # Ask the user which number they want.
        responseInt = -1
        isFirstPrint = True
        while True:
            try:
                if isFirstPrint:
                    isFirstPrint = False
                else:
                    Logger.Warn( "If you need help, contact us! https://octoeverywhere.com/support")
                response = input("Enter the number for the config you would like to setup now: ")
                response = response.lower().strip()
                # Parse the input and -1 it, so it aligns with the array length.
                tempInt = int(response.lower().strip()) - 1
                if tempInt >= 0 and tempInt < len(pairList):
                    responseInt = tempInt
                    break
                Logger.Warn("Invalid number selection, try again.")
            except Exception as e:
                Logger.Warn("Invalid input, try again. Logger.Error: "+str(e))

        # We have a selection, use it!
        context.MoonrakerConfigFilePath = pairList[responseInt].MoonrakerConfigFilePath
        context.MoonrakerServiceFileName = pairList[responseInt].ServiceFileName
        Logger.Info(f"Moonraker instance selected! [{context.MoonrakerServiceFileName}:{context.MoonrakerConfigFilePath}]")
        return


    def _FindAllServiceFilesAndPairings(self) -> list:
        # Look for any service file that matches moonraker*.service.
        # For simple installs, there will be one file called moonraker.service.
        # For more complex setups, we assume it will use the kiauh naming system, of moonraker-<name or number>.service
        serviceFiles = self._FindAllFiles(Util.SystemdServiceFilePath, "moonraker", ".service")

        # Based on the possible service files, see what moonraker config files we can match.
        results = []
        for f in serviceFiles:
            # Try to find a matching moonraker config file, based off the service file.
            moonrakerConfigPath = self._TryToFindMatchingMoonrakerConfig(f)
            if moonrakerConfigPath is None:
                Logger.Debug(f"Moonraker config file not found for service file [{f}]")
                try:
                    with open(f, "r", encoding="utf-8") as serviceFile:
                        lines = serviceFile.readlines()
                        for l in lines:
                            Logger.Debug(l)
                except Exception:
                    pass
            else:
                Logger.Debug(f"Moonraker service [{f}] matched to [{moonrakerConfigPath}]")
                # Only return fully matched pairs
                # Pair the service file and the moonraker config file path.
                results.append(ServiceFileConfigPathPair(os.path.basename(f), moonrakerConfigPath))
        return results


    def _FindAllFiles(self, path:str, prefix:str = None, suffix:str = None, depth:int = 0):
        results = []
        if depth > 10:
            return results
        # Use sorted, so the results are in a nice user presentable order.
        fileAndDirList = sorted(os.listdir(path))
        for fileOrDirName in fileAndDirList:
            fullFileOrDirPath = os.path.join(path, fileOrDirName)
            # Search sub folders
            if os.path.isdir(fullFileOrDirPath):
                tmp = self._FindAllFiles(fullFileOrDirPath, prefix, suffix, depth + 1)
                if tmp is not None:
                    for t in tmp:
                        results.append(t)
            # Only accept files that aren't links, since there are a lot of those in the service files.
            elif os.path.isfile(fullFileOrDirPath) and os.path.islink(fullFileOrDirPath) is False:
                include = True
                if prefix is not None:
                    include = fileOrDirName.lower().startswith(prefix)
                if include is True and suffix is not None:
                    include = fileOrDirName.lower().endswith(suffix)
                if include:
                    results.append(fullFileOrDirPath)
        return results


    def _TryToFindMatchingMoonrakerConfig(self, serviceFilePath:str) -> str or None:
        try:
            # Using the service file to try to find the moonraker config that's associated.
            Logger.Debug(f"Searching for moonraker config for {serviceFilePath}")
            with open(serviceFilePath, "r", encoding="utf-8") as serviceFile:
                lines = serviceFile.readlines()
                for l in lines:
                    # Search for the line that has the moonraker environment.
                    # Ex EnvironmentFile=/home/pi/printer_1_data/systemd/moonraker.env
                    if "moonraker.env" in l.lower():
                        Logger.Debug("Found moonraker.env line: "+l)

                        # When found, try to file the config path.
                        equalsPos = l.rfind('=')
                        if equalsPos == -1:
                            continue
                        # Move past the = sign.
                        equalsPos += 1

                        # Find the end of the path.
                        filePathEnd = l.find(' ', equalsPos)
                        if filePathEnd == -1:
                            filePathEnd = len(l)

                        # Get the file path.
                        # Sample path /home/pi/printer_1_data/systemd/moonraker.env
                        envFilePath = l[equalsPos:filePathEnd]
                        envFilePath = envFilePath.strip()

                        # From the env path, remove the file name and test if the config is in the same dir, which is not common.
                        searchConfigPath = Util.GetParentDirectory(envFilePath)
                        moonrakerConfigFilePath = self._FindMoonrakerConfigFromPath(searchConfigPath)
                        if moonrakerConfigFilePath is not None:
                            Logger.Debug("Moonraker config found in env dir")
                            return moonrakerConfigFilePath

                        # Move to the parent and look explicitly in the config folder, if there is one, this is where we expect to find it.
                        # We do this to prevent finding config files in other printer_data folders, like backup.
                        searchConfigPath = Util.GetParentDirectory(Util.GetParentDirectory(envFilePath))
                        searchConfigPath = os.path.join(searchConfigPath, "config")
                        if os.path.exists(searchConfigPath):
                            moonrakerConfigFilePath = self._FindMoonrakerConfigFromPath(searchConfigPath)
                            if moonrakerConfigFilePath is not None:
                                Logger.Debug("Moonraker config found in config dir")
                                return moonrakerConfigFilePath

                        # If we still didn't find it, move the printer_data root, and look one last time.
                        searchConfigPath = Util.GetParentDirectory(Util.GetParentDirectory(envFilePath))
                        moonrakerConfigFilePath = self._FindMoonrakerConfigFromPath(searchConfigPath)
                        if moonrakerConfigFilePath is not None:
                            Logger.Debug("Moonraker config found from printer data root")
                            return moonrakerConfigFilePath

                        Logger.Debug(f"No matching config file was found for line [{l}] in service file, looking for more lines...")
        except Exception as e:
            Logger.Warn(f"Failed to read service config file for config find.: {serviceFilePath} {str(e)}")
        return None


    # Recursively looks from the root path for the moonraker config file.
    def _FindMoonrakerConfigFromPath(self, path, depth = 0):
        if depth > 20:
            return None

        # Get all files and dirs in this dir
        fileAndDirList = os.listdir(path)

        # First, check all of the files.
        dirsToSearch = []
        for fileOrDirName in fileAndDirList:
            fullFileOrDirPath = os.path.join(path, fileOrDirName)
            fileNameOrDirLower = fileOrDirName.lower()
            # If we find a dir, cache it, so we check all of the files in this folder first.
            # This is important, because some OS images like RatOS have moonraker.conf files in nested folders
            # that we don't want to find first.
            if os.path.isdir(fullFileOrDirPath):
                dirsToSearch.append(fileOrDirName)
            # If it's a file, test if it.
            elif os.path.isfile(fullFileOrDirPath) and os.path.islink(fullFileOrDirPath) is False:
                # We use an exact match, to prevent things like moonraker.conf.backup from matching, which is common.
                if fileNameOrDirLower == "moonraker.conf":
                    return fullFileOrDirPath

        # We didn't find a matching file, process the sub dirs.
        for d in dirsToSearch:
            fullFileOrDirPath = os.path.join(path, d)
            fileNameOrDirLower = d.lower()
            # Ignore backup folders
            if fileNameOrDirLower == "backup":
                continue
            # For RatOS (a prebuilt pi image) there's a folder named RatOS in the config folder.
            # That folder is a git repo for the RatOS project, and it contains a moonraker.conf, but it's not the one we should target.
            # The community has told us to target the moonraker.conf in the ~/printer_data/config/
            # Luckily, this is quite a static image, so there aren't too many variants of it.
            if fileNameOrDirLower == "ratos":
                continue
            tempResult = self._FindMoonrakerConfigFromPath(fullFileOrDirPath, depth + 1)
            if tempResult is not None:
                return tempResult

        # We didn't find it.
        return None


    def _PrintDebugPaths(self, context:Context):
        # Print all service files.
        Logger.Debug("Discovery - Service Files")
        self._PrintAllFilesAndSubFolders(Util.SystemdServiceFilePath, ".service")

        # We want to print files that might be printer data folders or names of other folders on other systems.
        Logger.Blank()
        Logger.Debug("Discovery - Config Files In Home Path")
        self._PrintAllFilesAndSubFolders(context.UserHomePath, ".conf")


    def _PrintAllFilesAndSubFolders(self, path:str, targetSuffix:str, depth = 0, depthStr = " "):
        if depth > 5:
            return
        # Use sorted, so the results are in a nice user presentable order.
        fileAndDirList = sorted(os.listdir(path))
        for fileOrDirName in fileAndDirList:
            fullFileOrDirPath = os.path.join(path, fileOrDirName)
            # Print the file or folder if it starts with the target suffix.
            if fileOrDirName.lower().endswith(targetSuffix):
                Logger.Debug(f"{depthStr}{fullFileOrDirPath}")
            # Look through child folders.
            if os.path.isdir(fullFileOrDirPath):
                self._PrintAllFilesAndSubFolders(fullFileOrDirPath, targetSuffix, depth + 1, depthStr + "  ")