# Starling BMFont generation: starling_make_bmfont.py
# Creates BMFont XML+PNG
# python3 -m pip install rectpack pygame>=1.9.2 lxml
# Adapted from https://github.com/bendmorris/bmfg

import argparse
import os
import lxml.etree as ET
import pygame
import pygame.freetype
import rectpack

DEFAULT_CHARS = r''' !"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~АаБбВвГгДдЕеËëЖжЗзИиЙйКкЛлМмНнОоПпРрСсТтУуФфХхЦцЧчШшЩщЪъЫыЬьЭэЮюЯя'''
# DEFAULT_CHARS = r'''idA''' # kerning TEST
# DEFAULT_CHARS = r'''Група игы''' # Cyrillic TEST
SPECIAL_CHARS = {
    ' ': 'space'
}

def parse_color(c):
    if len(c) == 6:
        c += 'ff'
    elif len(c) != 8:
        raise Exception("Invalid color: {} (use RRGGBB or RRGGBBAA)".format(c))
    val = int(c, 16)
    return pygame.Color((val >> 24) & 0xff,
                        (val >> 16) & 0xff,
                        (val >> 8) & 0xff,
                        val & 0xff)

def set_alpha(surface, alpha):
    if alpha < 0xff:
        surface.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)

def upconvert(src_surface):
    surface = pygame.Surface((src_surface.get_width(), src_surface.get_height()), flags=pygame.SRCALPHA)
    surface.blit(src_surface, (0, 0))
    return surface

def premultiply_alpha(surface):
    #return pygame.image.fromstring(pygame.image.tostring(surface, 'RGBA_PREMULT'), surface.get_size(), 'RGBA')
    import numpy as np
    array = pygame.surfarray.pixels3d(surface)
    alpha = pygame.surfarray.pixels_alpha(surface)
    array[:,:,:] *= np.uint8(alpha[:,:,None] / 255.)

# def overflow(n):
#     if (n > 0 and n & 0x80000000):
#         n -= 0x100000000
#     return n

def run(args):
    pygame.display.init()
    # resolution=61 approx: Roboto-Regular TTF 36: 'sized_height' == font_size
    pygame.freetype.init(resolution=61)

    output_path = args.output or args.input_file
    output_name = os.path.splitext(os.path.basename(output_path))[0]
    output_dir = os.path.dirname(output_path)

    font_sizes = args.size
    visible_chars = sorted(set(args.chars))
    antialiasing = hasattr(args, 'antialiasing') and args.antialiasing
    color = parse_color(args.color)
    background_color = parse_color(args.background)
    border_color = parse_color(args.border_color)
    pt = args.padding if args.padding_top is None else args.padding_top
    pb = args.padding if args.padding_bottom is None else args.padding_bottom
    pl = args.padding if args.padding_left is None else args.padding_left
    pr = args.padding if args.padding_right is None else args.padding_right
    max_texture_size = args.max_texture_size
    texture_square = args.square
    pretty_print = args.pretty_print
    premultiply = args.premultiply
    kerning = args.kerning
    _border_width = args.border
    _char_spacing = args.char_spacing
    _line_spacing = args.line_spacing
    _pack_mode = args.pack_mode

    surfaces = {}
    kerning_data = {}

    def get_font(font_size):
        font_path = args.input_file
        print('Loading font',font_path, font_size)
        print('- antialised:', antialiasing,"| kerning:", kerning)
        font = pygame.freetype.Font(font_path, font_size)
        font.antialiased = antialiasing
        # dbg_text1,_ = font.render("iii III Ai!", (255, 0, 0), (255, 255, 255))
        # pygame.image.save(dbg_text1, os.path.join(os.path.dirname(font_path),"dbg_text1.png"))
        if kerning:
            font.kerning = True
            # dbg_text2,_ = font.render("iii III Ai!", (255, 0, 0), (255, 255, 255))
            # pygame.image.save(dbg_text2, os.path.join(os.path.dirname(font_path),"dbg_text2.png"))
        return font

    for font_size in font_sizes:
        surfaces[font_size] = {}

        base_size = args.base_size or font_size
        scale = float(font_size)/base_size
        border_width = int(_border_width * scale + 0.5)
        char_spacing = int(_char_spacing * scale + 0.5)
        line_spacing = int(_line_spacing * scale + 0.5)

        font = get_font(font_size)

        removed = set()
        for char in visible_chars:
            if font.get_metrics(char)[0] is None:
                removed.add(char)
        if removed:
            print('Removed the following unsupported chars: ' + ''.join(removed))
            visible_chars = [x for x in visible_chars if x not in removed]

        print('Rendering characters...')
        for char in visible_chars:
            bgcolor = pygame.Color(color.r, color.g, color.b, 0)
            glyph, g_rect = font.render(char, fgcolor=color, bgcolor=bgcolor)
            glyph_surface = upconvert(glyph)
            set_alpha(glyph_surface, color.a)
            w = max(1,glyph_surface.get_width() + pl + pr)
            h = max(1,glyph_surface.get_height() + pt + pb)
            # print('- render', char, (w,h), g_rect, font.get_metrics(char))
            char_surface = pygame.Surface((w, h), flags=pygame.SRCALPHA)
            if border_width > 0:
                bglyph_surface, _ = font.render(char, fgcolor=border_color, bgcolor=bgcolor)
                border_surface = pygame.Surface((w, h), flags=pygame.SRCALPHA)
                for a in range(0, border_width * 2 + 2):
                    for b in range(0, border_width * 2 + 2):
                        _a, _b = a - border_width, b - border_width
                        if ((_a * _a + _b * _b) ** 0.5) < border_width:
                            border_surface.blit(bglyph_surface, (pl + a, pt + b))
                set_alpha(border_surface, border_color.a)
                char_surface.blit(border_surface, (0, 0))
            char_surface.blit(glyph_surface, (pl + border_width, pt + border_width))
            surfaces[font_size][char] = char_surface

        if kerning:
            print('Experimental: Generating kerning data...')
            kerning_data[font_size] = {}
            for char1 in visible_chars:
                for char2 in visible_chars:
                    w1 = font.get_rect(char1).width
                    w2 = font.get_rect(char2).width
                    wc = font.get_rect(char1 + char2).width
                    if wc != w1 + w2:
                        kerning_data[font_size][(char1, char2)] = wc - w1 - w2
                    # # https://www.pygame.org/docs/ref/freetype.html#pygame.freetype.Font.get_metrics
                    # wm = font.get_metrics(char1 + char2)
                    # if len(wm) != 2:
                    #     continue
                    # print("- kerning", char1 + char2, (w1, w2, wc), wm)

    print('Packing...')
    print('- max_size:',max_texture_size,'| pack_mode:',_pack_mode)
    texture_width = max_texture_size
    texture_height = max_texture_size
    pack_rect_list = None
    if _pack_mode > 0:
        sizes = [128]
        while sizes[-1] * 2 <= max_texture_size:
            sizes.append(sizes[-1] * 2)
        texture_width, texture_height = sizes[0], sizes[0] / 2
        while texture_height < sizes[-1]:
            if texture_height < texture_width:
                texture_height *= 2
            else:
                texture_width *= 2
            packer = rectpack.newPacker(rotation=False)
            packer.add_bin(texture_width, texture_height, count=len(visible_chars))

            for font_size in font_sizes:
                for char, surface in surfaces[font_size].items():
                    su_w = surface.get_width()
                    su_h = surface.get_height()
                    packer.add_rect(su_w, su_h, (font_size, char))
            packer.pack()
            if len(packer) == 1:
                break
        pack_rect_list = packer.rect_list()
    else:
        # simple left-to-right fill, convenient for further photoshopping
        pack_rect_list = []
        p_bin = 0
        for font_size in font_sizes:
            max_w = 0
            max_h = 0
            for char, surface in surfaces[font_size].items():
                su_w = surface.get_width()
                su_h = surface.get_height()
                su_met = font.get_metrics(char)[0]
                max_w = max(max_w, su_w)
                max_h = max(max_h, su_h+abs(su_met[2]))
            x_c = 0
            y_c = 0
            for char, surface in surfaces[font_size].items():
                su_w = surface.get_width()
                su_h = surface.get_height()
                su_met = font.get_metrics(char)[0]
                # print("- charr",char,su_met)
                pack_rect_list.append( (p_bin, x_c + (max_w-su_w)*0.5, y_c + (max_h-su_h) - su_met[2], su_w, su_h, (font_size, char)) )
                x_c = x_c+max_w
                if x_c >= max_texture_size:
                    x_c = 0
                    y_c = y_c+max_h
            p_bin = p_bin+1

    if texture_square and texture_height < texture_width:
        texture_height = texture_width

    print('Generating textures...')
    textures = {}
    for b, x, y, w, h, (font_size, char) in pack_rect_list:
        b += 1
        if b not in textures:
            textures[b] = pygame.Surface((texture_width, texture_height), flags=pygame.SRCALPHA)
            textures[b].fill(background_color)
        textures[b].blit(surfaces[font_size][char], (x, y))

    texture_pages = []
    for texture_id, texture in textures.items():
        filename = os.path.join(output_dir, '{}_{}.png'.format(output_name, texture_id-1))
        print('Saving {}...'.format(filename))
        texture_pages.append(os.path.basename(filename))
        if premultiply:
            premultiply_alpha(texture)
        pygame.image.save(texture, filename)

    print('Generating font atlases...')
    for font_size in font_sizes:
        base_size = args.base_size or font_size
        scale = float(font_size)/base_size
        border_width = int(_border_width * scale + 0.5)
        char_spacing = int(_char_spacing * scale + 0.5)
        line_spacing = int(_line_spacing * scale + 0.5)

        font = get_font(font_size)
        base_height = font.get_sized_ascender()
        line_height = font.get_sized_height()
        line_height_pp = base_height # font.get_sized_glyph_height()+font.get_sized_descender()
        print("- font metrics", {"sized_height": font.get_sized_height(), "sized_glyph_height": font.get_sized_glyph_height(), "sized_ascender": font.get_sized_ascender(), "sized_descender": font.get_sized_descender(), "A-metric": font.get_metrics("A")[0]})
        filename = os.path.join(output_dir, '{}.fnt'.format(output_name))
        if len(font_sizes) > 1:
            filename = os.path.join(output_dir, '{}.{}.fnt'.format(output_name, font_size))
        root = ET.Element("font")
        info = ET.SubElement(root, "info", {'size': str(font_size), 'face': font.name, "smooth": "0"})
        if antialiasing:
            info.attrib["smooth"] = "1"
        common = ET.SubElement(root, "common", {'lineHeight': str(line_height + line_spacing)})
        common.attrib["base"] = str( base_height )
        pages = ET.SubElement(root, "pages")
        for page_id, page in enumerate(texture_pages):
            ET.SubElement(pages, "page", {'id': str(page_id), 'file': page})
        chars = ET.SubElement(root, "chars", {'count': str(len(visible_chars))})
        for b, x, y, w, h, (size, char) in pack_rect_list:
            if size != font_size: continue
            (min_x, max_x, min_y, max_y, x_advance, _) = font.get_metrics(char)[0]
            # min_x, max_x, min_y, max_y = map(overflow, (min_x, max_x, min_y, max_y))
            # print("- char", char, ord(char), (min_x,min_y), (char_w, char_h), (w, h))
            attrib = {}
            attrib['id'] = str(ord(char))
            attrib['page'] = str(b)
            attrib['x'] = str(x)
            attrib['y'] = str(y)
            attrib['width'] = str(w)
            attrib['height'] = str(h)
            attrib['xoffset'] = str(min_x)
            attrib['yoffset'] = str(int(0.5 + line_height_pp + line_spacing - h - min_y + pt))
            attrib['xadvance'] = str(int(0.5 + x_advance + char_spacing))
            attrib['chnl'] = '15'
            # attrib['letter'] = SPECIAL_CHARS.get(char, char)
            ET.SubElement(chars, "char", attrib)
        if kerning:
            kernings = ET.SubElement(root, "kernings", {'count': str(len(kerning_data[font_size]))})
            for (c1, c2), amt in kerning_data[font_size].items():
                attrib = {
                    'first': str(ord(c1)),
                    'second': str(ord(c2)),
                    'amount': str(amt),
                }
                ET.SubElement(root, "kerning", attrib)
        tree = ET.ElementTree(root)
        with open(filename, 'wb') as output_file:
            content = ET.tostring(tree, pretty_print=pretty_print)
            output_file.write(content)

    print('Done')
    pygame.quit()

def main():
    parser = argparse.ArgumentParser(description='bmfg')
    parser.add_argument('input_file', help='path to font file; output files will be saved in this directory')
    parser.add_argument('--output', '-o', nargs='?', default=None,
                        help='output file path (extension ignored, none for same as input file)')
    parser.add_argument('--size', '-s',
                        type=int, default=64, nargs='+',
                        help='font sizes')
    parser.add_argument('--base-size',
                        type=int, default=None,
                        help='if provided, scale borders/spacing by size/base-size')
    parser.add_argument('--padding', '-p', type=int, default=2,
                        help='padding (all sides)')
    parser.add_argument('--padding-top',
                        type=int, default=None,
                        help='top padding (overrides --padding)')
    parser.add_argument('--padding-bottom',
                        type=int, default=None,
                        help='bottom padding (overrides --padding)')
    parser.add_argument('--padding-left',
                        type=int, default=None,
                        help='left padding (overrides --padding)')
    parser.add_argument('--padding-right',
                        type=int, default=None,
                        help='right padding (overrides --padding)')
    parser.add_argument('--color', '-c',
                        default='ffffff',
                        help='font color (RRGGBB or RRGGBBAA)')
    parser.add_argument('--border', '-b',
                        type=int, default=0,
                        help='border width (default no border)')
    parser.add_argument('--border-color',
                        default='000000',
                        help='border color (RRGGBB or RRGGBBAA)')
    parser.add_argument('--background',
                        default='00000000',
                        help='background color (RRGGBB or RRGGBBAA)')
    parser.add_argument('--max-texture-size',
                        type=int, default=1024,
                        help='max texture width/height')
    parser.add_argument('--square',
                        action='store_true',
                        help='use the same size for texture width and height')
    parser.add_argument('--chars',
                        default=DEFAULT_CHARS,
                        help='character set to render')
    parser.add_argument('--antialiasing',
                        action='store_true',
                        help='use antialiasing when rendering glyphs')
    parser.add_argument('--premultiply',
                        action='store_true',
                        help='save textures with premultiplied alpha')
    parser.add_argument('--kerning',
                        action='store_true',
                        help='include kerning for character pairs. experimental, unstable')
    parser.add_argument('--char-spacing',
                        type=int, default=0,
                        help='extra space between characters')
    parser.add_argument('--line-spacing',
                        type=int, default=0,
                        help='extra space between lines')
    parser.add_argument('--pack-mode',
                        type=int, default=1,
                        help='0 - simple horizontal, 1 - smart')
    parser.add_argument('--pretty-print',
                        action='store_true',
                        help='use multiple lines and indentation for atlas')

    args = parser.parse_args()

    run(args)

if __name__ == '__main__':
    main()
