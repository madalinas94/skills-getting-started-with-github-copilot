// Ariile vieții pentru vision board, fiecare cu afirmațiile ei.
const AREAS = [
  { id: 'calatorii', label: 'Călătorii', affirmations: [
    'Lumea e galeria mea: Florența, Paris și Kyoto mă așteaptă.',
    'Colecționez apusuri, orașe frumoase și amintiri, nu lucruri.',
    'Călătoresc des, confortabil și cu inima deschisă.'
  ] },
  { id: 'succes', label: 'Succes', affirmations: [
    'Construiesc cu disciplină o carieră de care sunt mândră.',
    'Oportunitățile potrivite mă găsesc pentru că sunt pregătită.',
    'Munca mea contează, iar rezultatele mele vorbesc pentru mine.'
  ] },
  { id: 'carti', label: 'Cărți', affirmations: [
    'Citesc în fiecare zi; fiecare carte mă face mai înțeleaptă.',
    'Mintea mea e o bibliotecă aleasă cu grijă.',
    'Douăzeci de pagini pe zi, o viață întreagă de idei.'
  ] },
  { id: 'bani', label: 'Libertate financiară', affirmations: [
    'Banii vin la mine ușor și îi investesc cu înțelepciune.',
    'Sunt liberă financiar și generoasă cu cei dragi.',
    'Portofoliul meu crește, pas cu pas, an de an.'
  ] },
  { id: 'masina', label: 'Mașina visurilor', affirmations: [
    'Conduc mașina visurilor mele, cu eleganță și în siguranță.',
    'Fiecare drum e o bucurie, într-o mașină care îmi seamănă.'
  ] },
  { id: 'casa', label: 'Casa mea', affirmations: [
    'Casa mea e luminoasă, caldă și plină de frumusețe.',
    'Am un cămin în care liniștea și iubirea se simt de la ușă.',
    'Casa visurilor mele devine realitate.'
  ] },
  { id: 'iubire', label: 'Iubire adevărată', affirmations: [
    'Iubesc și sunt iubită, cu blândețe, respect și loialitate.',
    'Atrag o iubire sinceră, matură și frumoasă.',
    'Inima mea e deschisă pentru iubirea adevărată.'
  ] },
  { id: 'credinta', label: 'Credință și rugăciune', affirmations: [
    'Mă încred în Dumnezeu și în planul Lui pentru mine.',
    'Încep și închei ziua cu rugăciune și recunoștință.',
    'Credința îmi dă liniște, putere și lumină.'
  ] },
  { id: 'frumusete', label: 'Frumusețe', affirmations: [
    'Mă îngrijesc cu iubire; strălucesc din interior spre exterior.',
    'Sunt frumoasă, luminoasă și în pace cu oglinda.',
    'Ritualurile mele de îngrijire sunt momente de iubire de sine.'
  ] },
  { id: 'fit', label: 'Fit și sănătoasă', affirmations: [
    'Corpul meu e puternic, sănătos și plin de energie.',
    'Mă mișc în fiecare zi pentru că îmi iubesc corpul.',
    'Mănânc curat, dorm bine, mă simt minunat.'
  ] },
  { id: 'eleganta', label: 'Eleganță și rafinament', affirmations: [
    'Sunt rafinată, feminină și elegantă în gânduri, vorbe și gesturi.',
    'Eleganța mea e liniștită: calitate, nu cantitate.',
    'Port grația ca pe cea mai frumoasă bijuterie.'
  ] },
  { id: 'familie', label: 'Familia împreună', affirmations: [
    'Familia mea e împreună, sănătoasă și fericită.',
    'Casa noastră e plină de râsete, mese lungi și iubire.',
    'Suntem uniți, ne sprijinim și ne bucurăm unii de alții.'
  ] }
];

// Numele și afirmațiile urmează limba interfeței; originalele românești rămân în labelRo / affirmationsRo.
for (const a of AREAS) {
  const label = a.label, affirmations = a.affirmations;
  delete a.label;
  delete a.affirmations;
  Object.defineProperties(a, {
    labelRo: { value: label },
    affirmationsRo: { value: affirmations },
    label: { enumerable: true, get() { return tr(a.id)?.[0] || label; } },
    affirmations: { enumerable: true, get() { return tr(a.id)?.[1] || affirmations; } }
  });
}

function tr(id) {
  const lang = require('./i18n').lang();
  return lang === 'ro' ? null : require('./quotes-i18n').AREAS[lang]?.[id];
}

const byId = id => AREAS.find(a => a.id === id);

module.exports = { AREAS, byId };
