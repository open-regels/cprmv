from __future__ import annotations

import json
from pathlib import Path
import regalgo

# the cprmv.annotations python library contains usefull decorators for annotation of CPRMV metadata
from cprmv.annotations import is_based_on

@is_based_on("https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006353016", "Élections nationales (défaut) — conditions cumulatives Art. L.2", "Sont électeurs les Françaises et Français âgés de dix-huit ans accomplis, jouissant de leurs droits civils et politiques et n'étant dans aucun cas d'incapacité prévu par la loi.")
# not in effect anymore since 07 JUILLET 1974 : @is_based_on("...", "Élections nationales (défaut) — conditions cumulatives Art. L.3","")
# not in effect anymore since 09 DÉCEMBRE 1983 : @is_based_on("...", "Élections nationales (défaut) — conditions cumulatives Art. L.4","")
# not in effect anymore since 25 MARS 2019 : @is_based_on("...", "Élections nationales (défaut) — conditions cumulatives Art. L.5","")
@is_based_on("https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006353028", "Élections nationales (défaut) — conditions cumulatives Art. L.6","Ne doivent pas être inscrits sur la liste électorale, pendant le délai fixé par le jugement, ceux auxquels les tribunaux ont interdit le droit de vote et d'élection, par application des lois qui autorisent cette interdiction.")
# not in effect anymore since 12 JUIN 2010 : @is_based_on("", "Élections nationales (défaut) — conditions cumulatives Art. L.7")
@is_based_on("https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006527438/", "Élections municipales (context[\"type_election\"] == \"municipale\") - Nationalité française OU (citoyen UE + domicile en France)  ← Art. 88-3 C°", "La garantie des droits de l'homme et du citoyen nécessite une force publique : cette force est donc instituée pour l'avantage de tous, et non pour l'utilité particulière de ceux auxquels elle est confiée.")
@is_based_on("https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006353531", "Élections municipales (context[\"type_election\"] == \"municipale\") - Nationalité française OU (citoyen UE + domicile en France)  ← L.O. 227-1", "Les citoyens de l'Union européenne résidant en France, autres que les citoyens français, peuvent participer à l'élection des conseillers municipaux dans les mêmes conditions que les électeurs français, sous réserve des dispositions de la présente section. Les personnes mentionnées au premier alinéa sont considérées comme résidant en France si elles y ont leur domicile réel ou si leur résidence y a un caractère continu. Pour l'application de la présente section, l'élection des membres du Conseil de Paris est assimilée à celle des conseillers municipaux.")
@ruleset("civique.droit-vote.v1")
@validFrom("2026-01-01") # all legal references are valid from this valid from date (and if applicable until the validUntil date, which has been omitted in this case)
@publishedOn("2026-06-01") # note that the official publish date can be later than the valid from date.. a version published earlier valid for the same period is to be seen as getting replaced by this version from this given date on.. one will still need access to the earlier version.
@method("https://cprmv.regles.gouv.fr/methods/regalgo") # regles.gouv.fr specific method that combines python formalisation method with regles.gouv.fr as publication method etc.
@output_of("https://services.gouv.fr/ministere/interieur/elections") # refers to some service in services catalog linked to the competent authority (Ministère de l'Intérieur) responsible for the contents of this algorithm and other context information such as related life events (might be relevant relating to reaching the age of 18 as official life event perhaps)
class DroitVoteAlgorithm:
    """
    Éligibilité au droit de vote en France selon le Code électoral.

    Élections nationales (défaut) — conditions cumulatives Art. L.2 à L.7 :
        - Nationalité française
        - 18 ans ou plus
        - Non privé de droits civiques
        - Inscrit sur les listes électorales

    Élections municipales (context["type_election"] == "municipale") :
        - Nationalité française OU (citoyen UE + domicile en France)  ← Art. 88-3 C° / L.O. 227-1
        - Mêmes conditions d'âge, capacité et inscription
    """

    def __init__(self) -> None:
        _meta_path = Path(__file__).parent / "metadata.json"
        self._metadata = json.loads(_meta_path.read_text())

    @property
    def algo_id(self) -> str:
        return self._metadata["dct:identifier"]

    @property
    def regulation(self) -> dict[str, str]:
        return self.is_based_on

    def compute(self, algo_input: regalgo.AlgoInput) -> regalgo.AlgoResult:
        """
        Détermine si une personne a le droit de voter en France.

        Args:
            algo_input: Entrée contenant les attributs de la personne.

        Returns:
            AlgoResult avec True/False et la traçabilité complète.

        Raises:
            ValueError: Si l'âge est négatif.
        """
        nationalite = bool(algo_input.data["nationalite_francaise"])
        age = int(algo_input.data["age"])
        capacite = bool(algo_input.data["capacite_civique"])
        inscrit = bool(algo_input.data["inscrit_listes_electorales"])

        if age < 0:
            raise ValueError(f"L'âge doit être positif, reçu : {age}")

        type_election = algo_input.context.get("type_election", "nationale")

        if type_election == "municipale":
            citoyennete_ue = bool(algo_input.data.get("citoyennete_ue", False))
            domicile_france = bool(algo_input.data.get("domicile_france", False))
            # Art. 88-3 C° / L.O. 227-1 : citoyen UE résidant en France
            eligible_nationalite = nationalite or (citoyennete_ue and domicile_france)
        else:
            eligible_nationalite = nationalite
            citoyennete_ue = bool(algo_input.data.get("citoyennete_ue", False))
            domicile_france = bool(algo_input.data.get("domicile_france", False))

        peut_voter = eligible_nationalite and age >= 18 and capacite and inscrit

        return regalgo.AlgoResult(
            value=peut_voter,
            algo_id=self.algo_id,
            regulation=self.regulation,
            inputs_snapshot=algo_input.data,
            metadata={
                "type_election": type_election,
                "conditions": {
                    "eligible_nationalite": eligible_nationalite,
                    "nationalite_francaise": nationalite,
                    "citoyennete_ue_avec_domicile_france": citoyennete_ue and domicile_france,
                    "age_suffisant": age >= 18,
                    "capacite_civique": capacite,
                    "inscrit_listes_electorales": inscrit,
                },
            },
        )
