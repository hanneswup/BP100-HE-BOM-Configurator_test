"""Extract explicitly selected commercial codes from interactive PDF fields."""
import re
from io import BytesIO

CODE = re.compile(r'(?<![A-Z0-9])FBCA\d{4}(?!\d)', re.IGNORECASE)


def extract_codes(fields):
    found = set()
    for name, field in fields.items():
        value = field.get('/V')
        if value is None or str(value).strip().lower() in ('', '/off', 'off'):
            continue
        # Printed option lists and unselected checkbox names are not evidence.
        sources = [str(value)]
        if str(field.get('/FT')) == '/Btn':
            sources.append(str(name))
        for source in sources:
            found.update(match.upper() for match in CODE.findall(source))
    return found


def extract_visual_codes(pdf_bytes):
    """Read boxed selections on text-based BP100 HE revision 07/08 forms.

    Return None when the complete expected layout cannot be verified.
    """
    import numpy as np
    import pypdfium2 as pdfium
    from scipy import ndimage

    document = pdfium.PdfDocument(BytesIO(pdf_bytes))
    codes = [f'FBCA{n:04d}' for n in [*range(3), *range(201, 225), *range(1000, 1016)]]
    optional = 'FBCA1016'
    positions = {}
    pages = []
    for page_number in range(min(len(document), 4)):
        page = document[page_number]
        textpage = page.get_textpage()
        full_text = textpage.get_text_range()
        pages.append(full_text)
        for code in codes + [optional]:
            search = textpage.search(code, match_case=True)
            match = search.get_next()
            if match:
                if code in positions or search.get_next():
                    return None
                textpage.count_rects(*match)
                left, bottom, right, top = textpage.get_rect(0)
                positions[code] = (page_number, left, bottom, right, top)
    if not all(code in positions for code in codes):
        return None
    if not any(re.search(r'BP\s*100\s*HE\s*Rev\.\s*0[78]', text, re.I) for text in pages):
        return None
    if optional in positions:
        codes.append(optional)
    # Do not claim a complete supported selection when the document lists
    # additional commercial codes for which we do not inspect a checkbox.
    if {code.upper() for code in CODE.findall(' '.join(pages))} - set(codes):
        return None
    marked = set()
    for page_number in sorted({positions[c][0] for c in codes}):
        page = document[page_number]
        width, height = page.get_size()
        if abs(width - 595) > 10 or abs(height - 842) > 10:
            return None
        pixels = np.asarray(page.render(scale=2).to_pil().convert('RGB'))
        labels, _ = ndimage.label(np.min(pixels, axis=2) < 140)
        candidates = []
        for area in ndimage.find_objects(labels):
            if area is None:
                continue
            y, x = area
            w, h = x.stop-x.start, y.stop-y.start
            if 18 <= w <= 32 and 18 <= h <= 32 and x.start > width * 1.35:
                candidates.append((x, y))
        ordered = sorted((positions[c][4], c) for c in codes if positions[c][0] == page_number)
        ordered.reverse()
        used = set()
        for i, (top, code) in enumerate(ordered):
            _, left, bottom, right, _ = positions[code]
            y_code = 2 * (height - (top + bottom) / 2)
            next_y = 2 * (height - ordered[i+1][0]) if i+1 < len(ordered) else pixels.shape[0]
            matches = [(x, y) for x, y in candidates if -8 <= (y.start+y.stop)/2-y_code < 100 and (y.start+y.stop)/2 < next_y + 5]
            matches.sort(key=lambda box: abs((box[1].start+box[1].stop)/2-y_code))
            if not matches or (len(matches) > 1 and abs((matches[1][1].start+matches[1][1].stop)/2-y_code) - abs((matches[0][1].start+matches[0][1].stop)/2-y_code) < 5):
                return None
            x, y = matches[0]
            key = (x.start, y.start)
            if key in used:
                return None
            used.add(key)
            interior = pixels[y.start+4:y.stop-4, x.start+4:x.stop-4]
            ink = int((np.min(interior, axis=2) < 210).sum())
            if 4 <= ink < 12:
                return None
            if ink >= 12:
                marked.add(code)
    if len(marked.intersection(codes[:3])) != 1 or len(marked.intersection(codes[3:27])) != 1:
        return None
    return marked
