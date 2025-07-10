# -*- coding: utf-8 -*-
import logging
from PyPDF2 import PdfWriter

_logger = logging.getLogger(__name__)

# Monkey patch to fix PyPDF2 compatibility
if hasattr(PdfWriter, 'clone_reader_document_root') and not hasattr(PdfWriter, 'cloneReaderDocumentRoot'):
    PdfWriter.cloneReaderDocumentRoot = PdfWriter.clone_reader_document_root
    _logger.info("Applied PyPDF2 compatibility patch")