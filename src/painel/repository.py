from sqlalchemy.orm import Session

from src.painel.model import LinkPainel


class RepositorioLinkPainel:

    def __init__(self, db: Session):
        self.db = db

    def buscar_todos(self) -> dict[str, str]:
        return {link.chave: link.url for link in self.db.query(LinkPainel).all()}

    def salvar(self, chave: str, url: str | None) -> None:
        """Grava o link da chave; url None remove o link fixado."""
        link = self.db.get(LinkPainel, chave)
        if url is None:
            if link is not None:
                self.db.delete(link)
        elif link is None:
            self.db.add(LinkPainel(chave=chave, url=url))
        else:
            link.url = url
        self.db.commit()
