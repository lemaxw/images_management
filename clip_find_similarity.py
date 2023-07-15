import torch
import clip

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load('ViT-B/32', device=device)

def find_similarities(image, entities):
    image = preprocess(image).unsqueeze(0).to(device)

    tokenized_texts = clip.tokenize(entities, truncate=True).to(device)

    # Calculate embeddings
    with torch.no_grad():
        image_features = model.encode_image(image)
        text_features = model.encode_text(tokenized_texts)

    # Calculate similarity
    with torch.no_grad():
        similarities = (image_features @ text_features.T).softmax(dim=-1)

    # Convert tensor to list
    return similarities.cpu().numpy().tolist()[0]