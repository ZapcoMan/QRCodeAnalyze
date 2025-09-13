import pyzbar.pyzbar as pyzbar
from PIL import Image, ImageEnhance, ImageFilter
import sys
import logging
import numpy as np
try:
    import colorlog
    COLOR_LOGGING_AVAILABLE = True
except ImportError:
    COLOR_LOGGING_AVAILABLE = False

# 设置带颜色的日志记录
if COLOR_LOGGING_AVAILABLE:
    # 创建带颜色的日志格式
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'blue',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }
    )

    # 创建控制台处理器并设置格式
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler]
    )
else:
    # 如果colorlog不可用，使用默认的日志记录
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def decode_data(raw_data, encoding_list):
    """
    尝试按照给定的编码格式列表解码数据。

    :param raw_data: 需要解码的原始字节数据。
    :param encoding_list: 编码格式的列表。
    :return: 解码后的字符串，如果所有格式尝试失败则返回None。
    """
    for encoding in encoding_list:
        try:
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None

def preprocess_image(img):
    """
    预处理图像以提高二维码识别率

    :param img: 原始图像
    :return: 预处理后的图像列表（多种处理方式）
    """
    images = []

    # 原始图像
    images.append(("原始图像", img))

    # 转换为灰度图像
    gray_img = img.convert('L')
    images.append(("灰度图像", gray_img))

    # 增强对比度
    enhancer = ImageEnhance.Contrast(gray_img)
    contrast_img = enhancer.enhance(2.0)
    images.append(("高对比度图像", contrast_img))

    # 二值化处理
    threshold = 128
    binary_img = contrast_img.point(lambda x: 0 if x < threshold else 255, '1')
    images.append(("二值化图像", binary_img))

    # 尝试不同的阈值
    for threshold in [64, 192]:
        binary_img = contrast_img.point(lambda x: 0 if x < threshold else 255, '1')
        images.append((f"二值化图像(阈值{threshold})", binary_img))

    # 额外的预处理方法，专门针对Telegram二维码
    # 1. 高斯模糊去噪后再二值化
    blurred = gray_img.filter(ImageFilter.GaussianBlur(radius=1))
    blurred_binary = blurred.point(lambda x: 0 if x < 128 else 255, '1')
    images.append(("高斯模糊+二值化", blurred_binary))

    # 2. 锐化处理
    sharpened = img.filter(ImageFilter.SHARPEN)
    images.append(("锐化图像", sharpened))

    # 3. 颜色反转处理（针对反色二维码）
    inverted = Image.eval(gray_img, lambda x: 255 - x)
    images.append(("颜色反转图像", inverted))

    # 4. 尺寸放大（小尺寸二维码处理）
    large_img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    images.append(("放大图像", large_img))

    return images

def decode_qrcode(image_path):
    """
    解码给定路径下的二维码图像。

    :param image_path: 二维码图像文件的路径。
    """

    logging.info(f"开始解码二维码: {image_path}")
    # 尝试打开图像文件
    try:
        img = Image.open(image_path)
    except FileNotFoundError:
        logging.error(f"文件未找到: {image_path}")
        return
    except IOError:
        logging.error(f"无法打开文件: {image_path}")
        return

    # 使用pyzbar解码图像中的二维码
    try:
        # 尝试多种预处理方式
        processed_images = preprocess_image(img)
        decoded_objects = []

        for name, processed_img in processed_images:
            temp_objects = pyzbar.decode(processed_img)
            if temp_objects:
                decoded_objects = temp_objects
                logging.info(f"使用 {name} 成功解码")
                break

        # 如果所有预处理方式都失败，尝试使用不同配置
        if not decoded_objects:
            try:
                decoded_objects = pyzbar.decode(img, symbols=[pyzbar.ZBarSymbol.QRCODE])
            except AttributeError:
                decoded_objects = pyzbar.decode(img)

            if not decoded_objects:
                # 尝试所有支持的符号类型（使用异常处理确保兼容性）
                symbol_types = [
                    'QRCODE',
                    'EAN13',
                    'EAN8',
                    'CODE128',
                    'CODE39',
                    'UPCA',
                    'UPCE'
                ]

                for symbol_name in symbol_types:
                    if hasattr(pyzbar.ZBarSymbol, symbol_name):
                        symbol = getattr(pyzbar.ZBarSymbol, symbol_name)
                        try:
                            temp_objects = pyzbar.decode(img, symbols=[symbol])
                            if temp_objects:
                                decoded_objects = temp_objects
                                logging.info(f"使用 {symbol_name} 格式成功解码")
                                break
                        except Exception:
                            continue

        if decoded_objects:
            # 获取第一个解码对象的数据
            raw_data = decoded_objects[0].data
            barcode_type = decoded_objects[0].type

            # 尝试将原始数据解码为UTF-8字符串
            decoded_data = decode_data(raw_data, ['utf-8', 'gbk', 'gb2312'])
            if decoded_data:
                logging.info(f"二维码内容: {decoded_data}")
            else:
                # 如果文本解码失败，至少显示原始字节数据的十六进制表示
                hex_data = raw_data.hex()
                logging.info(f"二维码数据(HEX): {hex_data}")
                logging.warning("无法将二维码数据解码为文本格式")
        else:
            logging.warning("标准方法未能解码二维码，尝试额外的处理方法")

            # 针对Telegram二维码的特殊处理
            # 1. 尝试更激进的图像处理
            # 转换为RGBA模式再处理
            if img.mode != 'RGBA':
                rgba_img = img.convert('RGBA')
                decoded_objects = pyzbar.decode(rgba_img)
                if decoded_objects:
                    logging.info("RGBA转换后解码成功")

            # 2. 如果还是无法解码，输出一些诊断信息
            if not decoded_objects:
                # 检查是否包含多个二维码
                # 尝试裁剪图像的四个角分别解码
                width, height = img.size
                crops = [
                    ("左上角", (0, 0, width//2, height//2)),
                    ("右上角", (width//2, 0, width, height//2)),
                    ("左下角", (0, height//2, width//2, height)),
                    ("右下角", (width//2, height//2, width, height))
                ]

                for name, box in crops:
                    cropped_img = img.crop(box)
                    temp_objects = pyzbar.decode(cropped_img)
                    if temp_objects:
                        decoded_objects = temp_objects
                        logging.info(f"在裁剪区域 {name} 中成功解码")
                        break

            if decoded_objects:
                # 获取解码结果
                raw_data = decoded_objects[0].data
                decoded_data = decode_data(raw_data, ['utf-8', 'gbk', 'gb2312'])
                if decoded_data:
                    logging.info(f"二维码内容: {decoded_data}")
                else:
                    hex_data = raw_data.hex()
                    logging.info(f"二维码数据(HEX): {hex_data}")
                    logging.warning("无法将二维码数据解码为文本格式")
            else:
                logging.error("经过所有尝试后仍然无法解码二维码")
                logging.info("建议：确保二维码清晰完整，或尝试使用专门的二维码应用扫描")
    except Exception as e:
        logging.error(f"解码过程中发生错误: {e}")
        return

if __name__ == "__main__":
    try:
        image_path = input("请输入二维码图片的路径: ")
        decode_qrcode(image_path)
    except KeyboardInterrupt:
        logging.error("程序被中断")
        sys.exit(1)
