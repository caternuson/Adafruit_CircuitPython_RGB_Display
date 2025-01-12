# The MIT License (MIT)
#
# Copyright (c) 2017 Radomir Dopieralski and Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`adafruit_rgb_display.rgb`
====================================================

Base class for all RGB Display devices

* Author(s): Radomir Dopieralski, Michael McWethy
"""

import time
try:
    import struct
except ImportError:
    import ustruct as struct

import adafruit_bus_device.spi_device as spi_device

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_RGB_Display.git"

# This is the size of the buffer to be used for fill operations, in 16-bit
# units.
try:
    # If we're on CPython, try to set as large as possible
    import platform
    if "CPython" in platform.python_implementation():
        # check for FT232H special case
        try:
            import os
            if os.environ['BLINKA_FT232H']:
                # we are limited by pyftdi's max SPI payload
                from pyftdi.spi import SpiController
                _BUFFER_SIZE = SpiController.PAYLOAD_MAX_LENGTH // 2 # max bytes / bytes per pixel
        except KeyError:
            # otherwise set it to blit the whole thing
            _BUFFER_SIZE = 320 * 240
    else:
        # in case CircuitPython ever implements platform
        _BUFFER_SIZE = 256
except ImportError:
    # Otherwise set smaller MCU friendly size
    _BUFFER_SIZE = 256

def color565(r, g=0, b=0):
    """Convert red, green and blue values (0-255) into a 16-bit 565 encoding.  As
    a convenience this is also available in the parent adafruit_rgb_display
    package namespace."""
    try:
        r, g, b = r  # see if the first var is a tuple/list
    except TypeError:
        pass
    return (r & 0xf8) << 8 | (g & 0xfc) << 3 | b >> 3


class DummyPin:
    """Can be used in place of a ``DigitalInOut()`` when you don't want to skip it."""
    def deinit(self):
        """Dummy DigitalInOut deinit"""
        pass

    def switch_to_output(self, *args, **kwargs):
        """Dummy switch_to_output method"""
        pass

    def switch_to_input(self, *args, **kwargs):
        """Dummy switch_to_input method"""
        pass

    @property
    def value(self):
        """Dummy value DigitalInOut property"""
        pass

    @value.setter
    def value(self, val):
        pass

    @property
    def direction(self):
        """Dummy direction DigitalInOut property"""
        pass

    @direction.setter
    def direction(self, val):
        pass

    @property
    def pull(self):
        """Dummy pull DigitalInOut property"""
        pass

    @pull.setter
    def pull(self, val):
        pass

class Display: #pylint: disable-msg=no-member
    """Base class for all RGB display devices
        :param width: number of pixels wide
        :param height: number of pixels high
    """
    _PAGE_SET = None
    _COLUMN_SET = None
    _RAM_WRITE = None
    _RAM_READ = None
    _X_START = 0 # pylint: disable=invalid-name
    _Y_START = 0 # pylint: disable=invalid-name
    _INIT = ()
    _ENCODE_PIXEL = ">H"
    _ENCODE_POS = ">HH"
    _DECODE_PIXEL = ">BBB"

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.init()

    def init(self):
        """Run the initialization commands."""
        for command, data in self._INIT:
            self.write(command, data)

    #pylint: disable-msg=invalid-name,too-many-arguments
    def _block(self, x0, y0, x1, y1, data=None):
        """Read or write a block of data."""
        self.write(self._COLUMN_SET, self._encode_pos(x0 + self._X_START, x1 + self._X_START))
        self.write(self._PAGE_SET, self._encode_pos(y0 + self._Y_START, y1 + self._Y_START))
        if data is None:
            size = struct.calcsize(self._DECODE_PIXEL)
            return self.read(self._RAM_READ,
                             (x1 - x0 + 1) * (y1 - y0 + 1) * size)
        self.write(self._RAM_WRITE, data)
        return None
    #pylint: enable-msg=invalid-name,too-many-arguments

    def _encode_pos(self, x, y):
        """Encode a postion into bytes."""
        return struct.pack(self._ENCODE_POS, x, y)

    def _encode_pixel(self, color):
        """Encode a pixel color into bytes."""
        return struct.pack(self._ENCODE_PIXEL, color)

    def _decode_pixel(self, data):
        """Decode bytes into a pixel color."""
        return color565(*struct.unpack(self._DECODE_PIXEL, data))

    def pixel(self, x, y, color=None):
        """Read or write a pixel at a given position."""
        if color is None:
            return self._decode_pixel(self._block(x, y, x, y))

        if 0 <= x < self.width and 0 <= y < self.height:
            self._block(x, y, x, y, self._encode_pixel(color))
        return None

    def image(self, img, rotation=0):
        """Set buffer to value of Python Imaging Library image.  The image should
        be in 1 bit mode and a size equal to the display size."""
        if not img.mode in ('RGB', 'RGBA'):
            raise ValueError('Image must be in mode RGB or RGBA')
        if rotation not in (0, 90, 180, 270):
            raise ValueError('Rotation must be 0/90/180/270')
        if rotation != 0:
            img = img.rotate(rotation, expand=True)
        imwidth, imheight = img.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError('Image must be same dimensions as display ({0}x{1}).' \
                .format(self.width, self.height))
        pixels = bytearray(self.width * self.height * 2)
        # Iterate through the pixels
        for x in range(self.width):       # yes this double loop is slow,
            for y in range(self.height):  #  but these displays are small!
                pix = color565(img.getpixel((x, y)))
                pixels[2*(y * self.width + x)] = pix >> 8
                pixels[2*(y * self.width + x) + 1] = pix & 0xFF

        #print([hex(x) for x in pixels])
        self._block(0, 0, self.width-1, self.height - 1, pixels)

    #pylint: disable-msg=too-many-arguments
    def fill_rectangle(self, x, y, width, height, color):
        """Draw a rectangle at specified position with specified width and
        height, and fill it with the specified color."""
        x = min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, y))
        width = min(self.width - x, max(1, width))
        height = min(self.height - y, max(1, height))
        self._block(x, y, x + width - 1, y + height - 1, b'')
        chunks, rest = divmod(width * height, _BUFFER_SIZE)
        pixel = self._encode_pixel(color)
        if chunks:
            data = pixel * _BUFFER_SIZE
            for _ in range(chunks):
                self.write(None, data)
        self.write(None, pixel * rest)
    #pylint: enable-msg=too-many-arguments

    def fill(self, color=0):
        """Fill the whole display with the specified color."""
        self.fill_rectangle(0, 0, self.width, self.height, color)

    def hline(self, x, y, width, color):
        """Draw a horizontal line."""
        self.fill_rectangle(x, y, width, 1, color)

    def vline(self, x, y, height, color):
        """Draw a vertical line."""
        self.fill_rectangle(x, y, 1, height, color)


class DisplaySPI(Display):
    """Base class for SPI type devices"""
    #pylint: disable-msg=too-many-arguments
    def __init__(self, spi, dc, cs, rst=None, width=1, height=1,
                 baudrate=12000000, polarity=0, phase=0, *,
                 x_offset=0, y_offset=0):
        self.spi_device = spi_device.SPIDevice(spi, cs, baudrate=baudrate,
                                               polarity=polarity, phase=phase)
        self.dc_pin = dc
        self.rst = rst
        self.dc_pin.switch_to_output(value=0)
        if self.rst:
            self.rst.switch_to_output(value=0)
            self.reset()
        self._X_START = x_offset # pylint: disable=invalid-name
        self._Y_START = y_offset # pylint: disable=invalid-name
        super().__init__(width, height)
    #pylint: enable-msg=too-many-arguments

    def reset(self):
        """Reset the device"""
        self.rst.value = 0
        time.sleep(0.050)  # 50 milliseconds
        self.rst.value = 1
        time.sleep(0.050)  # 50 milliseconds

    # pylint: disable=no-member
    def write(self, command=None, data=None):
        """SPI write to the device: commands and data"""
        if command is not None:
            self.dc_pin.value = 0
            with self.spi_device as spi:
                spi.write(bytearray([command]))
        if data is not None:
            self.dc_pin.value = 1
            with self.spi_device as spi:
                spi.write(data)

    def read(self, command=None, count=0):
        """SPI read from device with optional command"""
        data = bytearray(count)
        self.dc_pin.value = 0
        with self.spi_device as spi:
            if command is not None:
                spi.write(bytearray([command]))
            if count:
                spi.readinto(data)
        return data
