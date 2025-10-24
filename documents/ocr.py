"""
OCR (Optical Character Recognition) System
Extract text from images using Tesseract
"""

from typing import Dict, Optional, BinaryIO
from PIL import Image
import pytesseract
import io
from pathlib import Path
from loguru import logger


class OCRProcessor:
    """
    Extract text from images
    Supports JPG, PNG, TIFF, BMP
    """

    def __init__(self):
        self.supported_formats = ['jpg', 'jpeg', 'png', 'tiff', 'tif', 'bmp']

        # Try to configure tesseract path (platform-specific)
        try:
            # Common locations
            possible_paths = [
                '/usr/bin/tesseract',
                '/usr/local/bin/tesseract',
                'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',
                '/opt/homebrew/bin/tesseract'
            ]

            for path in possible_paths:
                if Path(path).exists():
                    pytesseract.pytesseract.tesseract_cmd = path
                    logger.info(f"Tesseract configured at: {path}")
                    break
        except Exception as e:
            logger.warning(f"Could not configure tesseract path: {e}")

    async def extract_text_from_image(
        self,
        image_file: BinaryIO,
        filename: str,
        language: str = 'eng',
        config: Optional[str] = None
    ) -> Dict:
        """
        Extract text from image file

        Args:
            image_file: Image file object
            filename: Original filename
            language: OCR language (default: 'eng')
            config: Tesseract config string

        Returns:
            Dict with extracted text and confidence
        """
        try:
            # Check file extension
            file_extension = Path(filename).suffix.lower().replace('.', '')

            if file_extension not in self.supported_formats:
                raise ValueError(f"Unsupported image format: {file_extension}")

            # Open image
            image = Image.open(image_file)

            # Convert to RGB if necessary
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')

            # Apply preprocessing for better OCR
            image = self._preprocess_image(image)

            # Extract text
            text = pytesseract.image_to_string(image, lang=language, config=config or '')

            # Get confidence data
            try:
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang=language)
                confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            except Exception:
                avg_confidence = None

            # Get image metadata
            metadata = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode
            }

            logger.info(f"OCR extracted {len(text)} characters from {filename} (confidence: {avg_confidence})")

            return {
                "text": text.strip(),
                "confidence": avg_confidence,
                "metadata": metadata,
                "word_count": len(text.split()),
                "char_count": len(text)
            }

        except Exception as e:
            logger.error(f"Error performing OCR on {filename}: {e}", exc_info=True)
            raise

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR accuracy

        Args:
            image: PIL Image object

        Returns:
            Preprocessed image
        """
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')

            # Increase contrast
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)

            # Increase sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.5)

            return image

        except Exception as e:
            logger.warning(f"Error preprocessing image: {e}")
            return image

    async def extract_text_from_multiple_images(
        self,
        image_files: list,
        filenames: list,
        language: str = 'eng'
    ) -> list:
        """
        Extract text from multiple images

        Args:
            image_files: List of image file objects
            filenames: List of filenames
            language: OCR language

        Returns:
            List of extraction results
        """
        results = []

        for image_file, filename in zip(image_files, filenames):
            try:
                result = await self.extract_text_from_image(
                    image_file=image_file,
                    filename=filename,
                    language=language
                )
                result['filename'] = filename
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                results.append({
                    "filename": filename,
                    "error": str(e),
                    "text": "",
                    "confidence": 0
                })

        logger.info(f"Processed {len(results)} images with OCR")

        return results

    async def extract_with_layout_detection(
        self,
        image_file: BinaryIO,
        filename: str
    ) -> Dict:
        """
        Extract text with layout information
        Preserves structure and positioning

        Args:
            image_file: Image file object
            filename: Original filename

        Returns:
            Dict with structured text data
        """
        try:
            # Open image
            image = Image.open(image_file)

            # Preprocess
            image = self._preprocess_image(image)

            # Get detailed data
            data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                lang='eng'
            )

            # Organize by blocks and lines
            blocks = {}
            current_block = None
            current_line = None

            for i in range(len(data['text'])):
                if int(data['conf'][i]) < 30:  # Skip low confidence
                    continue

                block_num = data['block_num'][i]
                line_num = data['line_num'][i]
                word = data['text'][i].strip()

                if not word:
                    continue

                if block_num not in blocks:
                    blocks[block_num] = {}

                if line_num not in blocks[block_num]:
                    blocks[block_num][line_num] = []

                blocks[block_num][line_num].append({
                    "word": word,
                    "confidence": int(data['conf'][i]),
                    "x": data['left'][i],
                    "y": data['top'][i],
                    "width": data['width'][i],
                    "height": data['height'][i]
                })

            # Build structured text
            structured_text = []
            for block_num in sorted(blocks.keys()):
                block_lines = []
                for line_num in sorted(blocks[block_num].keys()):
                    line_text = " ".join(word['word'] for word in blocks[block_num][line_num])
                    block_lines.append(line_text)

                structured_text.append("\n".join(block_lines))

            full_text = "\n\n".join(structured_text)

            logger.info(f"Extracted text with layout from {filename}")

            return {
                "text": full_text,
                "structured_text": structured_text,
                "blocks": blocks,
                "block_count": len(blocks)
            }

        except Exception as e:
            logger.error(f"Error extracting text with layout: {e}")
            raise

    async def detect_document_type(self, text: str) -> str:
        """
        Attempt to detect document type from OCR text

        Args:
            text: Extracted text

        Returns:
            Document type string
        """
        try:
            text_lower = text.lower()

            # Check for common document types
            if any(word in text_lower for word in ['estimate', 'quote', 'proposal']):
                return 'estimate'
            elif any(word in text_lower for word in ['policy', 'coverage', 'insured']):
                return 'policy'
            elif any(word in text_lower for word in ['claim', 'adjuster', 'loss']):
                return 'claim_document'
            elif any(word in text_lower for word in ['invoice', 'bill', 'payment']):
                return 'invoice'
            elif any(word in text_lower for word in ['inspection', 'report', 'assessment']):
                return 'inspection_report'
            elif any(word in text_lower for word in ['photo', 'image', 'damage']):
                return 'photo_documentation'
            else:
                return 'unknown'

        except Exception as e:
            logger.error(f"Error detecting document type: {e}")
            return 'unknown'


# Global instance
ocr_processor = OCRProcessor()
