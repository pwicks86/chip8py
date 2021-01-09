import timeit
import logging
import random
import argparse
import msvcrt

import tkinter as tk
import threading

logging.basicConfig()
logger = logging.getLogger("chip8")
logger.setLevel(logging.DEBUG)
time_logger = logging.getLogger("time")
time_logger.setLevel(logging.DEBUG)

class TkinterRenderer(threading.Thread):
    def __init__(self, width, height, block_size = 16):
        threading.Thread.__init__(self)
        self.width = width
        self.height = height
        self.block_size = block_size
        self.start()

    def callback(self):
        self.root.quit()

    def run(self):
        self.root = tk.Tk()
        self.root.protocol("WM_DELETE_WINDOW", self.callback)

        # label = tk.Label(self.root, text="Hello World")
        # label.pack()
        self.canvas = tk.Canvas(self.root, bg = "dim gray", width=self.width * self.block_size, height = self.height * self.block_size)
        self.canvas.pack()

        self.root.mainloop()

    def update_screen(self, buffer):
        def updoot():
            self.canvas.delete("all")
            for col in range(self.width):
                for row in range(self.height):
                    if buffer[row * self.width + col] != 0:
                        top_row = row * self.block_size
                        left_col = col * self.block_size
                        bottom_row = (row + 1) * self.block_size
                        right_col = (col + 1) * self.block_size
                        self.canvas.create_rectangle(left_col, top_row, right_col, bottom_row, fill = "yellow")
        self.root.after_idle(updoot)

    
    def clear(self):
        def do_clear():
            self.canvas.delete("all")
        self.root.after(0, do_clear)


class Chip8:
    def __init__(self, renderer):
        self.renderer = renderer
        self.reset()

    def reset(self):
        self.memory = bytearray(4096)
        self.pc = 0x200
        self.i = 0x0
        self.gfx_buf = bytearray(64 * 32)
        self.delay_timer = 0
        self.sound_timer = 0
        self.sp = 0
        self.stack = [0 for i in range(16)]
        self.draw_flag = False
        self.v = { i:0 for i in range(0,16)}
        self.keys = { i:0 for i in range(0,16)}
        self.load_digits()
    
    def load_digits(self):
        hex_chars = [
            0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
            0x20, 0x60, 0x20, 0x20, 0x70,  # 1
            0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
            0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
            0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
            0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
            0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
            0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
            0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
            0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
            0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
            0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
            0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
            0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
            0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
            0xF0, 0x80, 0xF0, 0x80, 0x80  # F
        ]

        for i, val in enumerate(hex_chars):
            self.memory[i] = val
    
    def load_program(self, data):
        index = 0x200
        for b in data:
            self.memory[index] = b
            index += 1
        
    def update_keys(self):
        self.keys = { i:0 for i in range(0,16)}
        if msvcrt.kbhit():
            ret = msvcrt.getch()
            self.keys[int(ret)] = 1
            logger.warn("oh heay")

    def run_one_step(self):
        opcode = self.memory[self.pc] << 8 | self.memory[self.pc + 1]
        first_four = opcode & 0xF000
        nnn = opcode & 0x0FFF
        n = opcode & 0x000F
        kk = opcode & 0x00FF
        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4

        if opcode == 0x00E0:
            # Clear Screen
            logger.debug("CLS")
            self.renderer.clear()
            self.pc += 2
        elif opcode ==  0x00EE:
            # Return from subroutine
            logger.debug("RET")
            self.sp -= 1
            self.pc = self.stack[self.sp] 
            self.pc += 2
        elif first_four == 0x1000:
            # Unconditional Jump
            logger.debug(f"JMP {nnn}")
            self.pc = nnn
        elif first_four == 0x2000:
            # Call subroutine
            logger.debug(f"CALL {nnn}")
            self.stack[self.sp] = self.pc
            self.sp += 1
            self.pc = nnn
        elif first_four == 0x3000:
            # Skip next instruction if Vx == kk.
            logger.debug(f"SE V{x}, {kk}")
            if self.v[x] == kk:
                self.pc += 2
            self.pc += 2
        elif first_four == 0x4000:
            # Skip next instruction if Vx != kk.
            logger.debug(f"SNE V{x}, {kk}")
            if self.v[x] != kk:
                self.pc += 2
            self.pc += 2
        elif first_four == 0x5000:
            #Skip next instruction if Vx == Vy.
            logger.debug(f"SE V{x}, V{y}")
            if self.v[x] == self.v[y]:
                self.pc += 2
            self.pc += 2
        elif first_four == 0x6000:
            # Set Vx = kk.
            logger.debug(f"LD V{x}, {kk}")
            self.v[x] = kk
            self.pc += 2
        elif first_four == 0x7000:
            # Set Vx = Vx + kk.
            logger.debug(f"ADD V{x}, {kk}")
            self.v[x] = (self.v[x] + kk) & 0xFF
            self.pc += 2
        elif first_four == 0x8000:
            if n == 0x0:
                # Set Vx = Vy.
                logger.debug(f"LD V{x}, V{y}")
                self.v[x] = self.v[y]
                self.pc += 2
            elif n == 0x1:
                # Set Vx = Vx OR Vy.
                logger.debug(f"OR V{x}, V{y}")
                self.v[x] = self.v[x] | self.v[y]
                self.pc += 2
            elif n == 0x2:
                # Set Vx = Vx AND Vy.
                logger.debug(f"AND V{x}, V{y}")
                self.v[x] = self.v[x] & self.v[y]
                self.pc += 2
            elif n == 0x3:
                # Set Vx = Vx XOR Vy.
                logger.debug(f"XOR V{x}, V{y}")
                self.v[x] = self.v[x] ^ self.v[y]
                self.pc += 2

            elif n == 0x4:
                # Set Vx = Vx + Vy, set VF = carry.
                logger.debug(f"ADD V{x}, V{y}")
                val = self.v[x] + self.v[y]
                self.v[x] = val & 0xFF
                if val > 0xFF:
                    self.v[0xF] = 1
                else:
                    self.v[0xF] = 0
                self.pc += 2

            elif n == 0x5:
                # Set Vx = Vx - Vy, set VF = NOT borrow.
                logger.debug(f"SUB V{x}, V{y}")
                if self.v[x] > self.v[y]:
                    self.v[0xF] = 1
                else:
                    self.v[0xF] = 0 
                val = self.v[x] - self.v[y]
                self.v[x] = val & 0xFF
                self.pc += 2

            elif n == 0x6:
                # Set Vx = Vx SHR 1.
                logger.debug(f"SHR V{x}")
                if self.v[x] & 0x0001 == 1:
                    self.v[0xF] = 1
                else:
                    self.v[0xF] = 0
                self.v[x] = self.v[x] // 2
                self.pc += 2

            elif n == 0x7:
                # Set Vx = Vy - Vx, set VF = NOT borrow.
                logger.debug(f"SUBN V{x}, V{y}")
                if self.v[y] > self.v[x]:
                    self.v[0xF] = 1
                else:
                    self.v[0xF] = 0 
                val = self.v[x] - self.v[y]
                self.v[x] = val & 0xFF
                self.pc += 2

            elif n == 0xE:
                # Set Vx = Vx SHL 1.
                logger.debug(f"SHL V{x}")
                if self.v[x] >> 15 & 0x1 == 0x1:
                    self.v[0xF] = 1
                else:
                    self.v[0xF] = 0 
                self.v[x] = (self.v[x] * 2) & 0xFF
                self.pc += 2
            
            else:
                raise Exception("Invalid!")

        elif first_four == 0x9000:
            # Skip next instruction if Vx != Vy.
            logger.debug(f"SNE V{x}, V{y}")
            if self.v[x] != self.v[y]:
                self.pc += 2
            self.pc += 2
        
        elif first_four == 0xA000:
            # Set I = nnn.
            logger.debug(f"LD I, {nnn}")
            self.i = nnn
            self.pc += 2

        elif first_four == 0xB000:
            # Jump to location nnn + V0.
            logger.debug(f"JP V0, {nnn}")
            self.pc = nnn + self.v[0]

        elif first_four == 0xC000:
            # Set Vx = random byte AND kk.
            logger.debug(f"RND V{x}, {kk}")
            self.v[x] = (random.randint(0,0xFF) & kk) 
            self.pc += 2
        elif first_four == 0xD000:
            logger.debug(f"DRW V{x}, V{y}, {n}")
            x = self.v[x]
            y = self.v[y]
            height = n
            self.v[0xF] = 0
            for y_line in range(0, height):
                line = self.memory[self.i + y_line]
                for x_line in range(0,8):
                    if((line & (0x80 >> x_line)) != 0):
                        if(self.gfx_buf[(x + x_line + ((y + y_line) * 64))] == 1):
                            self.v[0xF] = 1                                 
                        self.gfx_buf[x + x_line + ((y + y_line) * 64)] ^= 1
 
            self.draw_flag = True
            self.pc += 2

            # Dxyn - DRW Vx, Vy, nibble
            # Display n-byte sprite starting at memory location I at (Vx, Vy), set VF = collision.

            # The interpreter reads n bytes from memory, starting at the address stored in I. 
            # These bytes are then displayed as sprites on screen at coordinates (Vx, Vy).
            # Sprites are XORed onto the existing screen. 
            # If this causes any pixels to be erased, VF is set to 1, otherwise it is set to 0. 
            # If the sprite is positioned so part of it is outside the coordinates of the display, it wraps around to the opposite side of the screen. 
            # See instruction 8xy3 for more information on XOR, and section 2.4, Display, for more information on the Chip-8 screen and sprites.
    
        elif first_four == 0xE000:
            if kk == 0x9E:
                # Skip next instruction if key with the value of Vx is pressed.
                logger.debug(f"SKP V{x}")
                if self.keys[self.v[x]] == 1:
                    self.pc += 2
                self.pc += 2
            elif kk == 0xA1:
                # Skip next instruction if key with the value of Vx is not pressed.
                logger.debug(f"SKNP V{x}")
                if self.keys[self.v[x]] != 1:
                    self.pc += 2
                self.pc += 2
            else:
                raise Exception("Oh no")
        elif first_four == 0xF000:
            if kk == 0x07:
                # Set Vx = delay timer value.
                logger.debug(f"LD V{x}, DT")
                self.v[x] = self.delay_timer
                self.pc += 2
            elif kk == 0x0A:
                # Wait for a key press, store the value of the key in Vx.
                logger.debug(f"LD V{x}, K")
                key = input()
                self.v[x] = key
                self.pc += 2
            elif kk == 0x15:
                # Set delay timer = Vx.
                logger.debug(f"LD DT, V{x}")
                self.delay_timer = self.v[x]
                self.pc += 2
            elif kk == 0x18:
                # Set sound timer = Vx.
                logger.debug(f"LD ST, V{x}")
                self.sound_timer = self.v[x]
                self.pc += 2
            elif kk == 0x1E:
                # Set I = I + Vx.
                logger.debug(f"ADD I, V{x}")
                self.i = (self.i + self.v[x]) & 0xFF
            elif kk == 0x29:
                # Fx29 - LD F, Vx
                # Set I = location of sprite for digit Vx.
                logger.debug(f"LD F, V{x}")

                # The value of I is set to the location for the hexadecimal sprite corresponding to the value of Vx. See section 2.4, Display, for more information on the Chip-8 hexadecimal font.
                # TODO
                raise(Exception("oh no"))

            elif kk == 0x33:
                # Store BCD representation of Vx in memory locations I, I+1, and I+2.
                logger.debug(f"LD B, V{x}")
                val = self.v[x]
                strval = str(val).zfill(3)
                hundreds = int(strval[0])
                tens = int(strval[1])
                ones = int(strval[2])
                self.memory[self.i] = hundreds
                self.memory[self.i + 1] = tens
                self.memory[self.i + 2] = ones
                self.pc += 2
            elif kk == 0x55:
                # Store registers V0 through Vx in memory starting at location I.
                logger.debug(f"LD [I], V{x}")
                index = self.i
                for i in range(0, x + 1):
                    self.memory[index] = self.v[i]
                    index += 1
                self.pc += 2
            elif kk == 0x65:
                # Read registers V0 through Vx from memory starting at location I.
                logger.debug(f"LD V{x}, [I]")
                index = self.i
                for i in range(0, x + 1):
                    self.v[i] = self.memory[index]
                    index += 1
                self.pc += 2

        if self.delay_timer > 0:
            self.delay_timer -= 1

        if self.sound_timer > 0:
            if sound_timer == 1:
                self.renderer.beep()
            self.sound_timer -= 1

    def render_screen(self):
        self.renderer.update_screen(self.gfx_buf)
        
    def run(self):
        while True:
            start_time = timeit.default_timer()
            self.run_one_step()
            elapsed = timeit.default_timer() - start_time
            time_logger.debug(f"time elapsed for step: {elapsed}")

            if self.draw_flag:
                start_time = timeit.default_timer()
                self.render_screen()
                elapsed = timeit.default_timer() - start_time
                time_logger.debug(f"time elapsed for render: {elapsed}")
            
            self.update_keys()
            


def run(program_path):
    with open(program_path, "rb") as f:
        prog_data = f.read()
    renderer = TkinterRenderer(64, 32)
    from time import sleep
    sleep(.1)
    chip8 = Chip8(renderer)
    chip8.load_program(prog_data)
    chip8.run()
    print("HI")

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description='Process some integers.')
    # run("test_opcode.ch8")
    # run("Minimal game [Revival Studios, 2007].ch8")
    # run("IBM Logo.ch8")
    # run("Keypad Test [Hap, 2006].ch8")
    # run("Clock Program [Bill Fisher, 1981].ch8")
    # run("Chip8 Picture.ch8")
    # run("Sirpinski [Sergey Naydenov, 2010].ch8")
    # run("Stars [Sergey Naydenov, 2010].ch8")
    # run("Trip8 Demo (2008) [Revival Studios].ch8")
    # run("Fishie [Hap, 2005].ch8")
    # run("Sirpinski [Sergey Naydenov, 2010].ch8")
    # run("Jumping X and O [Harry Kleinberg, 1977].ch8")
    # run("Framed MK2 [GV Samways, 1980].ch8")
    run("Chip8 emulator Logo [Garstyciuks].ch8")
