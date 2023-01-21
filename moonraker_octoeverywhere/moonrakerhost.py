import logging
import traceback

from octoeverywhere.mdns import MDns
from octoeverywhere.sentry import Sentry
from octoeverywhere.hostcommon import HostCommon
from octoeverywhere.telemetry import Telemetry
from octoeverywhere.octopingpong import OctoPingPong
from octoeverywhere.snapshothelper import SnapshotHelper
from octoeverywhere.octoeverywhereimpl import OctoEverywhere
from octoeverywhere.octohttprequest import OctoHttpRequest
from octoeverywhere.Proto.ServerHost import ServerHost

from .config import Config
from .logger import LoggerInit
from .uipopupinvoker import UiPopupInvoker
from .updatemanager import UpdateManager
from .version import Version

# This file is the main host for the moonraker service.
class MoonrakerHost:

    def __init__(self, klipperConfigDir, klipperLogDir) -> None:
        # When we create our class, make sure all of our core requirements are created.
        try:
            # First, we need to load our config.
            # Note that the config MUST BE WRITTEN into this folder, that's where the setup installer is going to look for it.
            # If this fails, it will throw.
            self.Config = Config(klipperConfigDir)

            # Next, setup the logger.
            self.Logger = LoggerInit.GetLogger(self.Config, klipperLogDir)

            # Init sentry, since it's needed for Exceptions.
            Sentry.Init(self.Logger, "klipper", True)

        except Exception as e:
            tb = traceback.format_exc()
            print("Failed to init Moonraker Host! "+str(e) + "; "+str(tb))
            # Raise the exception so we don't continue.
            raise


    def RunBlocking(self, klipperConfigDir, klipperLogDir, localStorageDir, serviceName, pyVirtEnvRoot, repoRoot):
        # Do all of this in a try catch, so we can log any issues before exiting
        try:
            self.Logger.info("##################################")
            self.Logger.info("#### OctoEverywhere Starting #####")
            self.Logger.info("##################################")

            # Find the version of the plugin, this is required and it will throw if it fails.
            pluginVersionStr = Version.GetPluginVersion(self.Logger, repoRoot)
            self.Logger.info("Plugin Version: %s", pluginVersionStr)

            # Before we do this first time setup, make sure our config files are in place. This is important
            # because if this fails it will throw. We don't want to let the user complete the install setup if things
            # with the update aren't working.
            UpdateManager.EnsureUpdateManagerFilesSetup(self.Logger, klipperConfigDir, serviceName, pyVirtEnvRoot, repoRoot)

            # Now, detect if this is a new instance and we need to init our global vars. If so, the setup script will be waiting on this.
            self.DoFirstTimeSetupIfNeeded(klipperConfigDir, serviceName)

            # Get our required vars
            printerId = self.GetPrinterId()
            privateKey = self.GetPrivateKey()

            # Init Sentry, but it won't report since we are in dev mode.
            Telemetry.Init(self.Logger)

            # Init the mdns client
            MDns.Init(self.Logger, localStorageDir)

            # Setup the http requester
            OctoHttpRequest.SetLocalHttpProxyPort(80)
            OctoHttpRequest.SetLocalHttpProxyIsHttps(False)
            OctoHttpRequest.SetLocalOctoPrintPort(80)

            # Init the ping pong helper.
            OctoPingPong.Init(self.Logger, localStorageDir, printerId)

            # TODO - Setup the notifications handler.
            #      - Setup SnapshotHelper
            #      - Kill Slipstream
            #      - Kill LocalAuth

            # Setup the snapshot helper
            SnapshotHelper.Init(self.Logger, None)

            oe = OctoEverywhere(HostCommon.c_OctoEverywhereOctoClientWsUri, printerId, privateKey, self.Logger, UiPopupInvoker(self.Logger), self, pluginVersionStr, ServerHost.Moonraker)
            oe.RunBlocking()
        except Exception as e:
            Sentry.Exception("!! Exception thrown out of main host run function.", e)

        # Allow the loggers to flush before we exit
        try:
            self.Logger.info("##################################")
            self.Logger.info("#### OctoEverywhere Exiting ######")
            self.Logger.info("##################################")
            logging.shutdown()
        except Exception as e:
            print("Exception in logging.shutdown "+str(e))


    # Ensures all required values are setup and valid before starting.
    def DoFirstTimeSetupIfNeeded(self, klipperConfigDir, serviceName):
        # Try to get the printer id from the config.
        isFirstRun = False
        printerId = self.Config.Get(Config.ServerSection, Config.PrinterIdKey, None)
        if HostCommon.IsPrinterIdValid(printerId) is False:
            if printerId is None:
                self.Logger.info("No printer id was found, generating one now!")
                # If there is no printer id, we consider this the first run.
                isFirstRun = True
            else:
                self.Logger.info("An invalid printer id was found [%s], regenerating!", str(printerId))

            # Make a new, valid, key
            printerId = HostCommon.GeneratePrinterId()

            # Save it
            self.Config.Set(Config.ServerSection, Config.PrinterIdKey, printerId)
            self.Logger.info("New printer id created: %s", printerId)

        privateKey = self.Config.Get(Config.ServerSection, Config.PrivateKeyKey, None)
        if HostCommon.IsPrivateKeyValid(privateKey) is False:
            if privateKey is None:
                self.Logger.info("No private key was found, generating one now!")
            else:
                self.Logger.info("An invalid private key was found [%s], regenerating!", str(privateKey))

            # Make a new, valid, key
            privateKey = HostCommon.GeneratePrivateKey()

            # Save it
            self.Config.Set(Config.ServerSection, Config.PrivateKeyKey, privateKey)
            self.Logger.info("New private key created.")

        # If this is the first run, do other stuff as well.
        if isFirstRun:
            UpdateManager.EnsureAllowedServicesFile(self.Logger, klipperConfigDir, serviceName)


    def GetPrinterId(self):
        return self.Config.Get(Config.ServerSection, Config.PrinterIdKey, None)


    def GetPrivateKey(self):
        return self.Config.Get(Config.ServerSection, Config.PrivateKeyKey, None)


    #
    # StatusChangeHandler Interface
    #
    def OnPrimaryConnectionEstablished(self, octoKey, connectedAccounts):
        self.Logger.info("OnPrimaryConnectionEstablished")


    #
    # StatusChangeHandler Interface
    #
    def OnPluginUpdateRequired(self):
        self.Logger.error("!!! A Plugin Update Is Required -- If This Plugin Isn't Updated It Might Stop Working !!!")
        self.Logger.error("!!! Please use the update manager in Mainsail of Fluidd to update this plugin         !!!")
