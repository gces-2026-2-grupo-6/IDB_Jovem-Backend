from sqlalchemy.orm import Session

from src.institucional.model import Institucional

# A tabela é um registro único: toda leitura e escrita usam esta chave.
ID_UNICO = 1


class RepositorioInstitucional:

    def __init__(self, db: Session):
        self.db = db

    def buscar(self) -> Institucional | None:
        return self.db.get(Institucional, ID_UNICO)

    def salvar(
        self,
        missao: str | None,
        visao: str | None,
        valores: list[str],
    ) -> Institucional:
        """Cria o registro único na primeira gravação e o atualiza depois."""
        conteudo = self.buscar()
        if conteudo is None:
            conteudo = Institucional(
                institucional_id=ID_UNICO,
                missao=missao,
                visao=visao,
                valores=list(valores),
            )
            self.db.add(conteudo)
        else:
            conteudo.missao = missao
            conteudo.visao = visao
            conteudo.valores = list(valores)
        self.db.commit()
        self.db.refresh(conteudo)
        return conteudo
