from PIL import Image

def resize_image(image_path, max_pixels):
    img = Image.open(image_path)
    width, height = img.size
    aspect_ratio = width / height

    if width + height > max_pixels:
        if aspect_ratio > 1:
            new_width = int(max_pixels / (1 + (1 / aspect_ratio)))
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = int(max_pixels / (1 + aspect_ratio))
            new_width = int(new_height * aspect_ratio)

        img = img.resize((new_width, new_height))

    return img
