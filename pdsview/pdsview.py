#! /usr/bin/env python

import sys
import os
import logging
try:
    import label
except:
    from pdsview import label
from glob import glob

from ginga.qtw.QtHelp import QtGui, QtCore
from ginga.qtw.ImageViewCanvasQt import ImageViewCanvas
from ginga.BaseImage import BaseImage
from planetaryimage import PDS3Image

STD_FORMAT = '%(asctime)s | %(levelname)1.1s | %(filename)s:%(lineno)d (%(funcName)s) | %(message)s'
#
#


class ImageStamp(BaseImage):
    """Assign each image attributes below and set the image with data"""
    def __init__(self, filepath, data_np=None, metadata=None, logger=None):
        BaseImage.__init__(self, data_np=data_np, metadata=metadata,
                           logger=logger)

        self.file_name = os.path.basename(filepath)
        try:
            pds_image = PDS3Image.open(filepath)
            self.set_data(pds_image.data)
            with open(filepath) as f:
                label_array = []
                for lineno, line in enumerate(f):
                    line = line.rstrip()
                    if line.strip() == 'END':
                        break

                    label_array.append(line)
            self.label = label_array
            self.pds_compatible = True
        except:
            self.pds_compatible = False

    def __repr__(self):
        return self.file_name


class ImageSet(object):
    """Create set of images to be displayed"""
    def __init__(self, filepaths):
        # Remove any duplicates
        seen = {}
        self.inlist = []
        for filepath in filepaths:
            if filepath not in seen:
                seen[filepath] = 1
                self.inlist.append(filepath)

        # Create image objects with attributes set in ImageStamp
        # These objects contain the data ginga will use to display the image
        self.images = []
        for filepath in self.inlist:
            self.image = ImageStamp(filepath)
            if self.image.pds_compatible:
                self.images.append(self.image)
        self.current_image_index = 0
        self.current_image = self.images[self.current_image_index]
        self.enable_next_previous()

    def enable_next_previous(self):
        """Set whether the next and previous buttons are enabled"""
        if len(self.images) > 1:
            self.next_prev_enabled = True
        else:
            self.next_prev_enabled = False

    def next(self):
        """Display next image, loop to first image if past the last image"""
        try:
            self.current_image_index += 1
            self.current_image = self.images[self.current_image_index]
        except:
            self.current_image_index = 0
            self.current_image = self.images[self.current_image_index]

    def previous(self):
        """Display previous image and loop to last image if past first image"""
        self.current_image_index -= 1
        if self.current_image_index < 0:
            self.current_image_index = len(self.images) - 1
        self.current_image = self.images[self.current_image_index]

    def append(self, new_file, dipslay_first_new_image):
        """Append a new image to the images list if pds compatible"""
        new_image = ImageStamp(new_file)
        if new_image.pds_compatible:
            self.images.append(new_image)
            self.enable_next_previous()
            self.current_image_index = dipslay_first_new_image
            self.current_image = self.images[self.current_image_index]
        return new_image


class PDSViewer(QtGui.QMainWindow):
    """Display a single image at a time with option specified in buttons"""

    def __init__(self, image_set):
        super(PDSViewer, self).__init__()

        self.images = image_set.images
        self.image_set = image_set

        # Set the subwindow names here. This implementation will help prevent
        # the main window from spawning duplicate children. Even if the
        # duplication prevention is not set up for a window, this will be a
        # handy reference list of windows(or dialogues in most cases) that can
        # be spawned out of this window.
        self._label_window = None

        self.pds_view = ImageViewCanvas(render='widget')
        self.pds_view.enable_autocuts('on')
        self.pds_view.set_autocut_params('zscale')
        self.pds_view.enable_autozoom('on')
        self.pds_view.set_callback('drag-drop', self.drop_file)
        self.pds_view.set_bg(0.5, 0.5, 0.5)
        self.pds_view.ui_setActive(True)

        self.pds_view.get_bindings().enable_all(True)

        pdsview_widget = self.pds_view.get_widget()
        pdsview_widget.resize(768, 768)

        vertical_align = QtGui.QVBoxLayout()
        vertical_align.setContentsMargins(QtCore.QMargins(2, 2, 2, 2))
        vertical_align.setSpacing(1)
        vertical_align.addWidget(pdsview_widget, stretch=1)

        horizontal_align = QtGui.QHBoxLayout()
        horizontal_align.setContentsMargins(QtCore.QMargins(4, 2, 4, 2))

        # self.open_label is need as an attribute to determine whether the user
        # should be able to open the label window. The other side of this
        # toggle is found in load_file().
        open_file = QtGui.QPushButton("Open File")
        open_file.clicked.connect(self.open_file)
        self.next_channel = QtGui.QPushButton("Next")
        self.next_channel.clicked.connect(
            lambda: self.display_image(next_image=True))
        self.next_channel.setEnabled(image_set.next_prev_enabled)
        self.previous_channel = QtGui.QPushButton("Previous")
        self.previous_channel.clicked.connect(
            lambda: self.display_image(previous_image=True))
        self.previous_channel.setEnabled(image_set.next_prev_enabled)
        self.open_label = QtGui.QPushButton("Label")
        self.open_label.clicked.connect(self.display_label)
        # self.open_label.setEnabled(False)
        quit_button = QtGui.QPushButton("Quit")
        quit_button.clicked.connect(self.quit)

        horizontal_align.addStretch(1)
        for button in (
                self.previous_channel, self.next_channel,
                open_file, self.open_label, quit_button):
            horizontal_align.addWidget(button, stretch=0)

        hw = QtGui.QWidget()
        hw.setLayout(horizontal_align)
        vertical_align.addWidget(hw, stretch=0)
        self.vertical_align = vertical_align
        self.horizontal_align = horizontal_align
        self.pdsview_widget = pdsview_widget

        vw = QtGui.QWidget()
        self.setCentralWidget(vw)
        vw.setLayout(vertical_align)

        self.display_image()

    def display_label(self):
        """Display the label over the image"""
        # Utilizing the subwindow variables to check if the label window has
        # been opened before. If not, the window is initialized.
        if self._label_window is None:
            self._label_window = label.LabelView(self)
        self._label_window.is_open = True
        self._label_window.show()
        self._label_window.activateWindow()

    def open_file(self):
        """Open a new image file from a file explorer"""
        filter = "IMG files (*.IMG)"
        file_name = QtGui.QFileDialog()
        file_name.setFileMode(QtGui.QFileDialog.ExistingFiles)
        opens = file_name.getOpenFileNames(self, "Open IMG files", ".", filter)
        if(opens[1] != ""):
            first_new_image = len(self.images)
            new_files = opens[0]
            for new_file in new_files:
                new_image = self.image_set.append(new_file, first_new_image)
                if not(new_image.pds_compatible):
                    print("%s is not PDS compatible" % (new_image.file_name))
            self.next_channel.setEnabled(self.image_set.next_prev_enabled)
            self.previous_channel.setEnabled(self.image_set.next_prev_enabled)
            self.display_image()
        else:
            # integrate with logger
            print("No file selected!")
            return

    def display_image(self, next_image=False, previous_image=False):
        """Display the current image and/or label"""
        if next_image:
            self.image_set.next()
        elif previous_image:
            self.image_set.previous()
        self.pds_view.set_image(self.image_set.current_image)
        self.image_label = self.image_set.current_image.label

        # This checks to see if the label window exists and is open. If so,
        # this resets the label field so that the label being displayed is the
        # label for the current product.
        if self._label_window is not None:
            label_text = '\n'.join(self.image_label)
            self._label_window.label_contents.setText(label_text)
            if self._label_window.is_open:
                self._label_window.cancel()
                self._label_window.show()
                self._label_window.is_open = True
                self._label_window.activateWindow()

        self.setWindowTitle(self.image_set.current_image.file_name)
        # save this line for testing purposes
        self.loaded_file = self.image_set.current_image.file_name
        self.open_label.setEnabled(True)

    def drop_file(self, pdsimage, paths):
        """This function is not yet supported"""
        # file_name = paths[0]
        # self.load_file(file_name)
        pass

    def quit(self, *args):
        """Close pdsview"""
        if self._label_window is not None:
            self._label_window.cancel()
        self.close()


def main():

    filepaths = glob('*')

    app = QtGui.QApplication(sys.argv)
    image_set = ImageSet(filepaths)

    w = PDSViewer(image_set)
    w.resize(780, 770)
    w.show()
    app.setActiveWindow(w)
    w.raise_()
    w.activateWindow()
    app.exec_()

if __name__ == '__main__':
    main()
