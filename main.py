import pyzbar.pyzbar as pyzbar
from PIL import Image
import sys
import logging

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def decode_data(raw_data, encoding_list):
    """
    尝试按照给定的编码格式列表解码数据。

    :param raw_data: 需要解码的原始字节数据。
    :param encoding_list: 编码格式的列表。
    :return: 解码后的字符串，如果所有格式尝试失败则返回None。
    """
    for encoding in encoding_list:
        try:
            logging.info(f"正在尝试编码格式: {encoding}")
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            logging.warning(f"当前 {encoding} 编码格式 解码失败，即将尝试下一个编码格式")
    return None

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
        decoded_objects = pyzbar.decode(img)
        logging.info(f"解码结果数量: {len(decoded_objects)}")

        if decoded_objects:
            # 获取第一个解码对象的数据
            raw_data = decoded_objects[0].data
            # 尝试将原始数据解码为UTF-8字符串
            decoded_data = decode_data(raw_data, ['utf-8', 'gbk', 'gb2312'])
            if decoded_data:
                logging.info(f"二维码内容: {decoded_data}")
            else:
                logging.error("无法解码二维码数据")
        else:
            logging.error("未能解码二维码")
    except Exception as e:
        logging.error(f"解码过程中发生错误: {e}")
        return

if __name__ == "__main__":
    try:
        image_path = input("请输入二维码图片的路径: ")
        # image_path = input("请输入二维码图片的路径: ")
        decode_qrcode(image_path)
    except KeyboardInterrupt:
        logging.error("程序被中断")
        sys.exit(1)
