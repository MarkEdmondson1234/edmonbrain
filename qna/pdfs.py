import sys, os
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

import pathlib
import logging

def split_pdf_to_pages(pdf_path, temp_dir):

    logging.info(f"Splitting PDF {pdf_path} into pages...")

    pdf_path = pathlib.Path(pdf_path)
    from pypdf import PdfReader, PdfWriter
    pdf = PdfReader(pdf_path)

    logging.info(f"PDF file {pdf_path} contains {len(pdf.pages)} pages")

    # Get base name without extension
    basename = os.path.splitext(os.path.basename(pdf_path))[0]

    page_files = []
    
    if len(pdf.pages) == 1:
        logging.info(f"Only one page in PDF {pdf_path} - sending back")
        return [str(pdf_path)]
    
    for page in range(len(pdf.pages)):
        pdf_writer = PdfWriter()
        pdf_writer.add_page(pdf.pages[page])

        output_filename = pathlib.Path(temp_dir, f'{basename}_p{page}.pdf')

        with open(output_filename, 'wb') as out:
            pdf_writer.write(out)

        logging.info(f'Created PDF page: {output_filename}')
        page_files.append(str(output_filename))

    logging.info(f"Split PDF {pdf_path} into {len(page_files)} pages...")
    return page_files
