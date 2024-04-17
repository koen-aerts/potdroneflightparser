from plyer.facades import FileChooser
from pyobjus import autoclass, protocol
from pyobjus.dylib_manager import load_framework


load_framework('/System/Library/Frameworks/Photos.framework')
load_framework('/System/Library/Frameworks/UniformTypeIdentifiers.framework')


class IOSFileChooser(FileChooser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_selection = None
        self._mime_type = None

    def _file_selection_dialog(self, *args, **kwargs):
        """
        Function called when action is required, A "mode" parameter specifies
        which and is one of "open", "save" or "dir".
        """
        self._on_selection = kwargs["on_selection"]
        self._mime_type = kwargs["mime_type"]
        if kwargs["mode"] == "open":
            self._open()
        else:
            raise NotImplementedError()

    def _get_picker(self):
        """
        Return an instantiated and configured UIImagePickerController.
        """
        mime_type = autoclass('UTType').typeWithMIMEType_(self._mime_type) # https://developer.apple.com/library/archive/documentation/Miscellaneous/Reference/UTIRef/Articles/System-DeclaredUniformTypeIdentifiers.html
        #mime_type = autoclass('NSString').alloc().initWithUTF8String_("com.pkware.zip-archive")
        mime_list = autoclass("NSArray").arrayWithObject_(mime_type)
        #picker = autoclass("UIDocumentMenuViewController")
        #print(f"######## UIDocumentMenuViewController")
        #print(dir(picker.alloc()))
        #picker = autoclass("UIDocumentPickerViewController") # This is the controller we want to use; probably requires some custom recipe in kivy-ios, see ios_filechooser.m for reference.
        picker = autoclass("UIDocumentBrowserViewController")
        #po = picker.alloc().initWithDocumentTypes_(mime_list, True)
        #po = picker.alloc().initWithDocumentTypes_inMode_(mime_list, 0)
        #po = picker.alloc().initForOpeningContentTypes_asCopy_(mime_list, True)
        po = picker.alloc().initForOpeningContentTypes_(mime_list)
        #po.modalPresentationStyle = 2 # UIModalPresentationFullScreen
        #po.definesPresentationContext = True
        po.allowsDocumentCreation = False
        #po.allowsMultipleSelection = False
        po.allowsPickingMultipleItems = False
        #po.shouldShowFileExtensions = True
        po.delegate = self
        return po

    def _open(self):
        """
        Launch the native iOS file browser. Upon selection, the
        `imagePickerController_didFinishPickingMediaWithInfo_` delegate is
        called where we close the file browser and handle the result.
        """
        picker = self._get_picker()
        print(f"_open 1...")
        UIApplication = autoclass('UIApplication')
        #print(f"######## UIApplication")
        #print(dir(UIApplication))
        #print(f"######## UIApplication.sharedApplication()")
        #print(dir(UIApplication.sharedApplication()))
        #print(f"######## UIApplication.sharedApplication().connectedScenes")
        #print(dir(UIApplication.sharedApplication().connectedScenes))
        #print(f"######## UIApplication.sharedApplication().connectedScenes.count")
        #print(dir(UIApplication.sharedApplication().connectedScenes.count))
        scenes = UIApplication.sharedApplication().connectedScenes.objectEnumerator()
        #print(f"######## UIApplication.sharedApplication().connectedScenes.objectEnumerator()")
        #print(dir(scenes))
        scene = scenes.nextObject()
        print(f"######## UIApplication.sharedApplication().connectedScenes.objectEnumerator().nextObject() 1")
        print(dir(scene))
        keyWindow = scene.keyWindow
        print(f"######## UIApplication.sharedApplication().connectedScenes.objectEnumerator().nextObject().keyWindow")
        print(dir(keyWindow))
        scene = scenes.nextObject()
        print(f"######## UIApplication.sharedApplication().connectedScenes.objectEnumerator().nextObject() 2")
        print(dir(scene))
        print(f"_open 2...")
        #vc = UIApplication.sharedApplication().keyWindow.rootViewController()
        vc = keyWindow.rootViewController()
        #vvc = vc.visibleViewController
        print(f"######### vc ...")
        print(dir(vc))
        #vc.presentModalViewController_animated_(picker, True)
        print(f"_open 3...")
        #vc.showViewController_sender_(picker, vc)
        vc.presentViewController_animated_completion_(picker, False, None)
        print(f"_open 4...")


    @protocol('UIDocumentBrowserViewControllerDelegate')
    def documentBrowser_didPickDocumentsAtURLs_(self, controller, urls):
        print(f"documentBrowser_didPickDocumentsAtURLs_ 1...")


    @protocol('UIDocumentPickerDelegate')
    def documentPicker_didPickDocumentsAtURLs_(self, controller, urls):
        print(f"documentPicker_didPickDocumentsAtURLs_ 1...")


    @protocol('UIDocumentPickerDelegate')
    def documentPicker_didPickDocumentAtURL_(self, controller, url):
        print(f"UIDocumentPickerDelegate 1...")
        """
        Delegate which handles the result of the image selection process.
        """
        controller.dismissViewControllerAnimated_completion_(True, None)
        print(f"UIDocumentPickerDelegate 2...")

        # Note: We need to call this Objective C class as there is currently
        #       no way to call a non-class function via pyobjus. And here,
        #       we have to use the `UIImagePNGRepresentation` to get the png
        #       representation. For this, please ensure you are using an
        #       appropriate version of kivy-ios.
        #native_image_picker = autoclass("NativeImagePicker").alloc().init()
        #print(f"UIDocumentPickerDelegate 3...")
        #path = native_image_picker.writeToPNG_(frozen_dict)
        #print(f"UIDocumentPickerDelegate 4...")
        #self._on_selection([path.UTF8String()])
