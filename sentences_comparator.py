from sentence_transformers import SentenceTransformer, util
import torch

# Initialize the Sentence-BERT model
model = SentenceTransformer('all-mpnet-base-v2')


class SentenceMatcher:
    """Reuse corpus embeddings and score multiple inputs in one model pass."""

    def __init__(self, statements):
        self.statements = list(statements)
        self.statement_embeddings = model.encode(self.statements, convert_to_tensor=True)

    def score_many(self, input_statements):
        input_statements = list(input_statements)
        if not input_statements:
            return []
        input_embeddings = model.encode(input_statements, convert_to_tensor=True)
        return util.pytorch_cos_sim(input_embeddings, self.statement_embeddings).tolist()

    def score(self, input_statement):
        return self.score_many([input_statement])[0]

def get_similar_sentences(input_statement, statements_set):
    return SentenceMatcher(statements_set).score(input_statement)
