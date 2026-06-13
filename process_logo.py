from PIL import Image
import os

def process_logo(input_path, output_path):
    try:
        if not os.path.exists(input_path):
            print(f"Error: {input_path} does not exist.")
            return

        img = Image.open(input_path)
        img = img.convert("RGBA")
        
        # Crop whitespace
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        
        # Resize if too large (keep aspect ratio)
        max_height = 150
        if img.height > max_height:
            ratio = max_height / img.height
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        img.save(output_path, format="PNG")
        print(f"Logo processed and saved to {output_path}")

    except Exception as e:
        print(f"Error processing logo: {e}")

if __name__ == "__main__":
    # Ensure assets dir exists
    if not os.path.exists("assets"):
        os.makedirs("assets")
        
    process_logo("assets/logo.ico", "assets/logo.png")
