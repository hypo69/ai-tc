from logger import logger
import argparse
from src.rag import build_rules_index

def main() -> None:
    """Запуск переиндексации Core RAG индекса."""
    parser = argparse.ArgumentParser(description='Переиндексация Core RAG индекса.')
    parser.add_argument('--fresh', action='store_true', help='Создать новый индекс с нуля.')
    args = parser.parse_args()
    logger.console(f'Запуск переиндексации Core RAG правил (fresh={args.fresh})...')
    index_path, docs_path = build_rules_index()
    logger.console(f'Successfully сгенерирован RAG индекс: {index_path}, {docs_path}')
if __name__ == '__main__':
    main()
