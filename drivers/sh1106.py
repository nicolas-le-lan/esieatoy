# sh1106.py -- Driver MicroPython pour OLED SH1106 (1.3")
import time
import framebuf

SET_CONTRAST        = 0x81
SET_NORM_INV        = 0xA6
SET_DISP            = 0xAE
SET_SCAN_DIR        = 0xC0
SET_SEG_REMAP       = 0xA0
SET_CHARGE_PUMP     = 0x8D
SET_COL_ADDR_LOW    = 0x00
SET_COL_ADDR_HIGH   = 0x10
SET_PAGE_ADDR       = 0xB0

class SH1106(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        for cmd in (
            0xAE,           # Display OFF
            0x40,           # Set Start Line
            0xB0,           # Set Page Address
            0x81, 0x7F,     # Set Contrast
            0xA1,           # Segment Remap (Reverse)
            0xA6,           # Normal Display
            0xA8, 0x3F,     # Multiplex Ratio 64
            0xC8,           # COM Scan Direction (Reverse)
            0xD3, 0x00,     # Display Offset 0
            0xD5, 0x80,     # Display Clock Div
            0xD9, 0x22,     # Pre-charge Period
            0xDA, 0x12,     # COM Pins Hardware Config
            0xDB, 0x40,     # VCOMH Deselect Level
            0xAD, 0x8B,     # DC-DC Control Mode
            0xAF,           # Display ON
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def show(self):
        for page in range(self.pages):
            self.write_cmd(0xB0 | page) # Page
            # SH1106 2px column offset
            self.write_cmd(0x02) # Low col
            self.write_cmd(0x10) # High col
            self.write_data(self.buffer[page * self.width : (page + 1) * self.width])

    def write_cmd(self, cmd):
        raise NotImplementedError

    def write_data(self, buf):
        raise NotImplementedError

class SH1106_I2C(SH1106):
    def __init__(self, width, height, i2c, addr=0x3F, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x00 # Co=0, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        data = bytearray(1 + len(buf))
        data[0] = 0x40
        data[1:] = buf
        self.i2c.writeto(self.addr, data)
