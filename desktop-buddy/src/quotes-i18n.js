// Citatele, mantra și afirmațiile în mai multe limbi. Listele sunt paralele cu cele românești
// (același index = aceeași idee), ca rotația zilnică să rămână la fel în orice limbă.
const store = require('./store');

const LANGS = ['ro', 'en', 'fr', 'es', 'it', 'de'];
const NAMES = { ro: 'Română', en: 'English', fr: 'Français', es: 'Español', it: 'Italiano', de: 'Deutsch' };
const AI_NAMES = { ro: 'română', en: 'engleză', fr: 'franceză', es: 'spaniolă', it: 'italiană', de: 'germană' };

const META = {
  ro: { locale: 'ro-RO', q: ['„', '”'], kicker: 'Mantra zilei', affNote: 'Spune-o cu voce tare, de trei ori, și crede-o.',
    labels: { citat: 'Citatul zilei', vorba: 'Vorba de duh', cuvant: 'Cuvântul zilei', motivatie: 'Motivația zilei', filozofie: 'Ideea zilei', afirmatie: 'Afirmația zilei' } },
  en: { locale: 'en-GB', q: ['“', '”'], kicker: 'Mantra of the day', affNote: 'Say it out loud, three times, and believe it.',
    labels: { citat: 'Quote of the day', vorba: 'Words of wit', cuvant: 'Word of the day', motivatie: 'Today’s motivation', filozofie: 'Idea of the day', afirmatie: 'Affirmation of the day' } },
  fr: { locale: 'fr-FR', q: ['« ', ' »'], kicker: 'Mantra du jour', affNote: 'Dis-la à voix haute, trois fois, et crois-y.',
    labels: { citat: 'Citation du jour', vorba: 'Mot d’esprit', cuvant: 'Le mot du jour', motivatie: 'Motivation du jour', filozofie: 'L’idée du jour', afirmatie: 'Affirmation du jour' } },
  es: { locale: 'es-ES', q: ['«', '»'], kicker: 'Mantra del día', affNote: 'Dilo en voz alta, tres veces, y créetelo.',
    labels: { citat: 'Cita del día', vorba: 'Frase ingeniosa', cuvant: 'Palabra del día', motivatie: 'Motivación del día', filozofie: 'Idea del día', afirmatie: 'Afirmación del día' } },
  it: { locale: 'it-IT', q: ['«', '»'], kicker: 'Mantra del giorno', affNote: 'Dilla ad alta voce, tre volte, e credici.',
    labels: { citat: 'Citazione del giorno', vorba: 'Battuta di spirito', cuvant: 'Parola del giorno', motivatie: 'Motivazione del giorno', filozofie: 'Idea del giorno', afirmatie: 'Affermazione del giorno' } },
  de: { locale: 'de-DE', q: ['„', '“'], kicker: 'Mantra des Tages', affNote: 'Sprich es dreimal laut aus – und glaube daran.',
    labels: { citat: 'Zitat des Tages', vorba: 'Geistreiches', cuvant: 'Wort des Tages', motivatie: 'Motivation des Tages', filozofie: 'Gedanke des Tages', afirmatie: 'Affirmation des Tages' } }
};

// ---------- colecția mantrei (aceeași ordine ca în mantra.js) ----------
const LIBRARY = {
  en: {
    citat: [
      ['It is not because things are difficult that we do not dare; it is because we do not dare that they are difficult.', 'Seneca'],
      ['Simplicity is the ultimate sophistication.', 'Leonardo da Vinci'],
      ['Elegance is not about being noticed, it’s about being remembered.', 'Giorgio Armani'],
      ['We are what we repeatedly do.', 'Will Durant, on Aristotle'],
      ['The future belongs to those who believe in the beauty of their dreams.', 'Eleanor Roosevelt'],
      ['Art washes away from the soul the dust of everyday life.', 'Pablo Picasso'],
      ['Risk comes from not knowing what you’re doing.', 'Warren Buffett'],
      ['The happiness of your life depends upon the quality of your thoughts.', 'Marcus Aurelius']
    ],
    vorba: [
      'Don’t rush to be busy. Rush to matter to what matters.',
      'One elegant “no” is worth more than ten tired “yeses”.',
      'Perfectionism is procrastination in expensive clothes.',
      'Lipstick can be retouched; a missed opportunity, not so easily.',
      'Your calendar shows what you truly love.',
      'Your inbox is other people’s to-do list. Be careful who writes your day.',
      'Coffee opens your eyes; focus opens doors.'
    ],
    cuvant: [
      ['The art of making difficult things look effortless.', 'Today: prepare thoroughly, then present with ease.'],
      ['Your reason for getting up in the morning.', 'Today: write in one sentence why your work matters.'],
      ['Continuous improvement, in small steps.', 'Today: do one thing 1% better than yesterday.'],
      ['A calm mind that nothing outside can disturb.', 'Today: don’t act on the first impulse. Breathe, then choose.'],
      ['The warm comfort of simple things.', 'Today: a candle, a book, ten minutes just for you.'],
      ['Putting soul, creativity and love into what you do.', 'Today: leave your mark on something small.'],
      ['The beauty of imperfection and of passing things.', 'Today: “good enough” is sometimes perfect.'],
      ['Flourishing: a life lived at its fullest potential.', 'Today: ask yourself what would make you proud tonight.']
    ],
    motivatie: [
      'Don’t wait to feel ready. Readiness comes from moving.',
      'Do today what the you of next year will thank you for.',
      'Two hours of true focus beat eight hours of busyness.',
      'Discipline is the highest form of self-love.',
      'It doesn’t have to be easy. It just has to be worth it.',
      'Your standards build your life. Keep them high, with grace.',
      'Confidence isn’t knowing you’ll succeed; it’s knowing you’ll be fine either way.'
    ],
    filozofie: [
      ['The dichotomy of control', 'Some things are within our power, others are not.', 'Epictetus', 'Today: put your energy only into the first.'],
      ['Amor fati', 'Love your fate, with everything it brings.', 'Nietzsche', 'Today: find the lesson in today’s obstacle.'],
      ['Memento mori', 'Time is the one resource you cannot get back.', 'The Stoics', 'Today: don’t waste it on things that don’t matter.'],
      ['The golden mean', 'Virtue lies between two extremes.', 'Aristotle', 'Today: neither too much nor too little. Balance.'],
      ['Carpe diem', 'Seize the day, trusting as little as possible in tomorrow.', 'Horace', 'Today: take the first step on the thing you keep postponing.'],
      ['Premeditatio malorum', 'Imagine the obstacles in advance, so they don’t surprise you.', 'Seneca', 'Today: what could go wrong? Prepare plan B.']
    ]
  },
  fr: {
    citat: [
      ['Ce n’est pas parce que les choses sont difficiles que nous n’osons pas, c’est parce que nous n’osons pas qu’elles sont difficiles.', 'Sénèque'],
      ['La simplicité est la sophistication suprême.', 'Léonard de Vinci'],
      ['L’élégance, ce n’est pas se faire remarquer, c’est qu’on se souvienne de vous.', 'Giorgio Armani'],
      ['Nous sommes ce que nous faisons de manière répétée.', 'Will Durant, sur Aristote'],
      ['L’avenir appartient à ceux qui croient à la beauté de leurs rêves.', 'Eleanor Roosevelt'],
      ['L’art lave notre âme de la poussière du quotidien.', 'Pablo Picasso'],
      ['Le risque vient de ne pas savoir ce que l’on fait.', 'Warren Buffett'],
      ['Le bonheur de ta vie dépend de la qualité de tes pensées.', 'Marc Aurèle']
    ],
    vorba: [
      'Ne te presse pas d’être occupée. Presse-toi d’être importante pour ce qui compte.',
      'Un « non » élégant vaut mieux que dix « oui » fatigués.',
      'Le perfectionnisme, c’est la procrastination en robe de soirée.',
      'Le rouge à lèvres se retouche ; une occasion manquée, beaucoup moins.',
      'Ton agenda montre ce que tu aimes vraiment.',
      'Ta boîte mail, c’est la liste de priorités des autres. Choisis qui écrit ta journée.',
      'Le café ouvre les yeux ; la concentration ouvre les portes.'
    ],
    cuvant: [
      ['L’art de rendre les choses difficiles faciles en apparence.', 'Aujourd’hui : prépare-toi à fond, puis présente avec légèreté.'],
      ['La raison pour laquelle tu te lèves le matin.', 'Aujourd’hui : écris en une phrase pourquoi ton travail compte.'],
      ['L’amélioration continue, à petits pas.', 'Aujourd’hui : fais une seule chose 1 % mieux qu’hier.'],
      ['La paix de l’esprit que rien d’extérieur ne trouble.', 'Aujourd’hui : ne réagis pas au premier élan. Respire, puis choisis.'],
      ['Le confort chaleureux des choses simples.', 'Aujourd’hui : une bougie, un livre, dix minutes rien que pour toi.'],
      ['Mettre son âme, sa créativité et son amour dans ce que l’on fait.', 'Aujourd’hui : laisse ton empreinte sur un petit détail.'],
      ['La beauté de l’imperfection et de l’éphémère.', 'Aujourd’hui : « assez bien » est parfois parfait.'],
      ['L’épanouissement : une vie vécue à son meilleur potentiel.', 'Aujourd’hui : demande-toi ce qui te rendrait fière ce soir.']
    ],
    motivatie: [
      'N’attends pas de te sentir prête. On le devient en avançant.',
      'Fais aujourd’hui ce dont la toi de l’an prochain te remerciera.',
      'Deux heures de vraie concentration valent mieux que huit heures d’agitation.',
      'La discipline est la plus haute forme d’amour de soi.',
      'Ça n’a pas besoin d’être facile. Ça doit juste en valoir la peine.',
      'Tes exigences construisent ta vie. Garde-les hautes, avec grâce.',
      'La confiance, ce n’est pas savoir que tu réussiras ; c’est savoir que tout ira bien quoi qu’il arrive.'
    ],
    filozofie: [
      ['La dichotomie du contrôle', 'Certaines choses dépendent de nous, d’autres non.', 'Épictète', 'Aujourd’hui : mets ton énergie seulement dans les premières.'],
      ['Amor fati', 'Aime ton destin, avec tout ce qu’il apporte.', 'Nietzsche', 'Aujourd’hui : trouve la leçon de l’obstacle du jour.'],
      ['Memento mori', 'Le temps est la seule ressource que l’on ne récupère pas.', 'Les stoïciens', 'Aujourd’hui : ne le gaspille pas pour ce qui ne compte pas.'],
      ['Le juste milieu', 'La vertu se tient entre deux extrêmes.', 'Aristote', 'Aujourd’hui : ni trop, ni trop peu. L’équilibre.'],
      ['Carpe diem', 'Cueille le jour présent, en te fiant le moins possible au lendemain.', 'Horace', 'Aujourd’hui : fais le premier pas vers ce que tu repousses.'],
      ['Premeditatio malorum', 'Imagine les obstacles à l’avance pour qu’ils ne te surprennent pas.', 'Sénèque', 'Aujourd’hui : qu’est-ce qui pourrait mal tourner ? Prépare un plan B.']
    ]
  },
  es: {
    citat: [
      ['No es porque las cosas sean difíciles que no nos atrevemos; es porque no nos atrevemos que son difíciles.', 'Séneca'],
      ['La simplicidad es la máxima sofisticación.', 'Leonardo da Vinci'],
      ['La elegancia no consiste en ser notada, sino en ser recordada.', 'Giorgio Armani'],
      ['Somos lo que hacemos repetidamente.', 'Will Durant, sobre Aristóteles'],
      ['El futuro pertenece a quienes creen en la belleza de sus sueños.', 'Eleanor Roosevelt'],
      ['El arte lava del alma el polvo de la vida cotidiana.', 'Pablo Picasso'],
      ['El riesgo viene de no saber lo que estás haciendo.', 'Warren Buffett'],
      ['La felicidad de tu vida depende de la calidad de tus pensamientos.', 'Marco Aurelio']
    ],
    vorba: [
      'No te apresures a estar ocupada. Apresúrate a importar en lo que importa.',
      'Un «no» elegante vale más que diez «sí» cansados.',
      'El perfeccionismo es la procrastinación vestida de gala.',
      'El pintalabios se retoca; una oportunidad perdida, no tanto.',
      'Tu agenda muestra lo que de verdad amas.',
      'Tu bandeja de entrada es la lista de prioridades de otros. Cuida quién escribe tu día.',
      'El café abre los ojos; la concentración abre puertas.'
    ],
    cuvant: [
      ['El arte de hacer que lo difícil parezca fácil.', 'Hoy: prepárate a fondo y luego preséntalo con naturalidad.'],
      ['La razón por la que te levantas cada mañana.', 'Hoy: escribe en una frase por qué tu trabajo importa.'],
      ['Mejora continua, en pequeños pasos.', 'Hoy: haz una sola cosa un 1 % mejor que ayer.'],
      ['La serenidad que nada exterior puede perturbar.', 'Hoy: no reacciones al primer impulso. Respira y luego elige.'],
      ['El cálido confort de las cosas sencillas.', 'Hoy: una vela, un libro, diez minutos solo para ti.'],
      ['Poner alma, creatividad y amor en lo que haces.', 'Hoy: deja tu huella en un pequeño detalle.'],
      ['La belleza de la imperfección y de lo efímero.', 'Hoy: «suficientemente bueno» a veces es perfecto.'],
      ['El florecimiento: una vida vivida en su mejor potencial.', 'Hoy: pregúntate qué te haría sentir orgullosa esta noche.']
    ],
    motivatie: [
      'No esperes a sentirte preparada. La preparación llega en el camino.',
      'Haz hoy lo que tu yo del año que viene te agradecerá.',
      'Dos horas de concentración real valen más que ocho de ajetreo.',
      'La disciplina es la forma más alta de amor propio.',
      'No tiene que ser fácil. Solo tiene que merecer la pena.',
      'Tus estándares construyen tu vida. Mantenlos altos, con elegancia.',
      'La confianza no es saber que lo lograrás; es saber que estarás bien pase lo que pase.'
    ],
    filozofie: [
      ['La dicotomía del control', 'Algunas cosas dependen de nosotros; otras, no.', 'Epicteto', 'Hoy: pon tu energía solo en las primeras.'],
      ['Amor fati', 'Ama tu destino, con todo lo que trae.', 'Nietzsche', 'Hoy: encuentra la lección en el obstáculo del día.'],
      ['Memento mori', 'El tiempo es el único recurso que no se recupera.', 'Los estoicos', 'Hoy: no lo malgastes en lo que no importa.'],
      ['El justo medio', 'La virtud está entre dos extremos.', 'Aristóteles', 'Hoy: ni demasiado ni demasiado poco. Equilibrio.'],
      ['Carpe diem', 'Aprovecha el día, confiando lo menos posible en el mañana.', 'Horacio', 'Hoy: da el primer paso en lo que sigues posponiendo.'],
      ['Premeditatio malorum', 'Imagina los obstáculos de antemano para que no te sorprendan.', 'Séneca', 'Hoy: ¿qué podría salir mal? Prepara un plan B.']
    ]
  },
  it: {
    citat: [
      ['Non è perché le cose sono difficili che non osiamo; è perché non osiamo che sono difficili.', 'Seneca'],
      ['La semplicità è la suprema sofisticazione.', 'Leonardo da Vinci'],
      ['L’eleganza non è farsi notare, ma farsi ricordare.', 'Giorgio Armani'],
      ['Siamo ciò che facciamo ripetutamente.', 'Will Durant, su Aristotele'],
      ['Il futuro appartiene a coloro che credono nella bellezza dei propri sogni.', 'Eleanor Roosevelt'],
      ['L’arte lava via dall’anima la polvere della vita quotidiana.', 'Pablo Picasso'],
      ['Il rischio nasce dal non sapere quello che si sta facendo.', 'Warren Buffett'],
      ['La felicità della tua vita dipende dalla qualità dei tuoi pensieri.', 'Marco Aurelio']
    ],
    vorba: [
      'Non avere fretta di essere occupata. Abbi fretta di contare per ciò che conta.',
      'Un «no» elegante vale più di dieci «sì» stanchi.',
      'Il perfezionismo è la procrastinazione in abito da sera.',
      'Il rossetto si ritocca; un’occasione persa, molto meno.',
      'La tua agenda mostra ciò che ami davvero.',
      'La tua casella di posta è la lista di priorità degli altri. Scegli chi scrive la tua giornata.',
      'Il caffè apre gli occhi; la concentrazione apre le porte.'
    ],
    cuvant: [
      ['L’arte di far sembrare facili le cose difficili.', 'Oggi: preparati a fondo, poi presenta con disinvoltura.'],
      ['Il motivo per cui ti alzi la mattina.', 'Oggi: scrivi in una frase perché il tuo lavoro conta.'],
      ['Miglioramento continuo, a piccoli passi.', 'Oggi: fai una sola cosa l’1% meglio di ieri.'],
      ['La quiete della mente che nulla di esterno può turbare.', 'Oggi: non reagire al primo impulso. Respira, poi scegli.'],
      ['Il caldo conforto delle cose semplici.', 'Oggi: una candela, un libro, dieci minuti solo per te.'],
      ['Mettere anima, creatività e amore in ciò che fai.', 'Oggi: lascia la tua impronta in un piccolo dettaglio.'],
      ['La bellezza dell’imperfezione e delle cose effimere.', 'Oggi: «abbastanza buono» a volte è perfetto.'],
      ['La fioritura: una vita vissuta al suo pieno potenziale.', 'Oggi: chiediti cosa ti renderebbe fiera stasera.']
    ],
    motivatie: [
      'Non aspettare di sentirti pronta. Si diventa pronte camminando.',
      'Fai oggi ciò per cui la te dell’anno prossimo ti ringrazierà.',
      'Due ore di vera concentrazione valgono più di otto ore di agitazione.',
      'La disciplina è la forma più alta di amore per se stesse.',
      'Non deve essere facile. Deve solo valerne la pena.',
      'I tuoi standard costruiscono la tua vita. Tienili alti, con grazia.',
      'La fiducia non è sapere che riuscirai; è sapere che starai bene comunque.'
    ],
    filozofie: [
      ['La dicotomia del controllo', 'Alcune cose dipendono da noi, altre no.', 'Epitteto', 'Oggi: metti la tua energia solo nelle prime.'],
      ['Amor fati', 'Ama il tuo destino, con tutto ciò che porta.', 'Nietzsche', 'Oggi: trova la lezione nell’ostacolo di oggi.'],
      ['Memento mori', 'Il tempo è l’unica risorsa che non si recupera.', 'Gli stoici', 'Oggi: non sprecarlo per ciò che non conta.'],
      ['Il giusto mezzo', 'La virtù sta tra due estremi.', 'Aristotele', 'Oggi: né troppo né troppo poco. Equilibrio.'],
      ['Carpe diem', 'Cogli l’attimo, confidando il meno possibile nel domani.', 'Orazio', 'Oggi: fai il primo passo verso ciò che continui a rimandare.'],
      ['Premeditatio malorum', 'Immagina gli ostacoli in anticipo, così non ti sorprenderanno.', 'Seneca', 'Oggi: cosa potrebbe andare storto? Prepara un piano B.']
    ]
  },
  de: {
    citat: [
      ['Nicht weil es schwer ist, wagen wir es nicht, sondern weil wir es nicht wagen, ist es schwer.', 'Seneca'],
      ['Einfachheit ist die höchste Stufe der Vollendung.', 'Leonardo da Vinci'],
      ['Bei Eleganz geht es nicht darum, bemerkt zu werden, sondern darum, in Erinnerung zu bleiben.', 'Giorgio Armani'],
      ['Wir sind, was wir wiederholt tun.', 'Will Durant, über Aristoteles'],
      ['Die Zukunft gehört denen, die an die Schönheit ihrer Träume glauben.', 'Eleanor Roosevelt'],
      ['Kunst wäscht den Staub des Alltags von der Seele.', 'Pablo Picasso'],
      ['Risiko entsteht, wenn man nicht weiß, was man tut.', 'Warren Buffett'],
      ['Das Glück deines Lebens hängt von der Beschaffenheit deiner Gedanken ab.', 'Marc Aurel']
    ],
    vorba: [
      'Beeil dich nicht, beschäftigt zu sein. Beeil dich, für das Wichtige wichtig zu sein.',
      'Ein elegantes „Nein“ ist mehr wert als zehn müde „Ja“.',
      'Perfektionismus ist Aufschieberitis im Abendkleid.',
      'Lippenstift lässt sich nachziehen; eine verpasste Chance kaum.',
      'Dein Kalender zeigt, was du wirklich liebst.',
      'Dein Posteingang ist die Prioritätenliste anderer. Achte darauf, wer deinen Tag schreibt.',
      'Kaffee öffnet die Augen; Fokus öffnet Türen.'
    ],
    cuvant: [
      ['Die Kunst, Schwieriges mühelos wirken zu lassen.', 'Heute: gründlich vorbereiten, dann entspannt präsentieren.'],
      ['Der Grund, warum du morgens aufstehst.', 'Heute: Schreib in einem Satz, warum deine Arbeit zählt.'],
      ['Stetige Verbesserung in kleinen Schritten.', 'Heute: Mach eine einzige Sache 1 % besser als gestern.'],
      ['Seelenruhe, die nichts von außen stören kann.', 'Heute: Reagiere nicht auf den ersten Impuls. Atme, dann entscheide.'],
      ['Die warme Geborgenheit einfacher Dinge.', 'Heute: eine Kerze, ein Buch, zehn Minuten nur für dich.'],
      ['Seele, Kreativität und Liebe in das legen, was man tut.', 'Heute: Hinterlass deine Handschrift in einem kleinen Detail.'],
      ['Die Schönheit des Unvollkommenen und Vergänglichen.', 'Heute: „Gut genug“ ist manchmal perfekt.'],
      ['Aufblühen: ein Leben, das sein bestes Potenzial entfaltet.', 'Heute: Frag dich, was dich heute Abend stolz machen würde.']
    ],
    motivatie: [
      'Warte nicht, bis du dich bereit fühlst. Bereitschaft entsteht im Gehen.',
      'Tu heute, wofür dir dein Ich im nächsten Jahr danken wird.',
      'Zwei Stunden echter Fokus schlagen acht Stunden Hektik.',
      'Disziplin ist die höchste Form der Selbstliebe.',
      'Es muss nicht leicht sein. Es muss sich nur lohnen.',
      'Deine Ansprüche bauen dein Leben. Halte sie hoch – mit Anmut.',
      'Selbstvertrauen heißt nicht zu wissen, dass du Erfolg hast, sondern dass es dir so oder so gut gehen wird.'
    ],
    filozofie: [
      ['Die Dichotomie der Kontrolle', 'Manches liegt in unserer Macht, anderes nicht.', 'Epiktet', 'Heute: Steck deine Energie nur in das Erste.'],
      ['Amor fati', 'Liebe dein Schicksal, mit allem, was es bringt.', 'Nietzsche', 'Heute: Finde die Lektion im Hindernis des Tages.'],
      ['Memento mori', 'Zeit ist die eine Ressource, die du nicht zurückbekommst.', 'Die Stoiker', 'Heute: Verschwende sie nicht an Unwichtiges.'],
      ['Die goldene Mitte', 'Die Tugend liegt zwischen zwei Extremen.', 'Aristoteles', 'Heute: nicht zu viel, nicht zu wenig. Balance.'],
      ['Carpe diem', 'Pflücke den Tag und vertraue möglichst wenig auf den morgigen.', 'Horaz', 'Heute: Mach den ersten Schritt bei dem, was du ständig aufschiebst.'],
      ['Premeditatio malorum', 'Stell dir Hindernisse vorher vor, damit sie dich nicht überraschen.', 'Seneca', 'Heute: Was könnte schiefgehen? Bereite Plan B vor.']
    ]
  }
};

// ---------- ariile vieții: nume și afirmații ----------
const AREAS = {
  en: {
    calatorii: ['Travel', ['The world is my gallery: Florence, Paris and Kyoto are waiting for me.', 'I collect sunsets, beautiful cities and memories, not things.', 'I travel often, comfortably and with an open heart.']],
    succes: ['Success', ['I am building, with discipline, a career I am proud of.', 'The right opportunities find me because I am prepared.', 'My work matters, and my results speak for me.']],
    carti: ['Books', ['I read every day; every book makes me wiser.', 'My mind is a carefully curated library.', 'Twenty pages a day, a lifetime of ideas.']],
    bani: ['Financial freedom', ['Money comes to me easily and I invest it wisely.', 'I am financially free and generous with those I love.', 'My portfolio grows, step by step, year after year.']],
    masina: ['Dream car', ['I drive the car of my dreams, elegantly and safely.', 'Every road is a joy, in a car that feels like me.']],
    casa: ['My home', ['My home is bright, warm and full of beauty.', 'I have a home where peace and love are felt from the doorstep.', 'My dream home is becoming reality.']],
    iubire: ['True love', ['I love and am loved, with tenderness, respect and loyalty.', 'I attract a sincere, mature and beautiful love.', 'My heart is open to true love.']],
    credinta: ['Faith and prayer', ['I trust in God and in His plan for me.', 'I begin and end my day with prayer and gratitude.', 'Faith gives me peace, strength and light.']],
    frumusete: ['Beauty', ['I care for myself with love; I glow from the inside out.', 'I am beautiful, radiant and at peace with the mirror.', 'My self-care rituals are moments of self-love.']],
    fit: ['Fit and healthy', ['My body is strong, healthy and full of energy.', 'I move every day because I love my body.', 'I eat clean, sleep well and feel wonderful.']],
    eleganta: ['Elegance and refinement', ['I am refined, feminine and elegant in thought, word and gesture.', 'My elegance is quiet: quality, not quantity.', 'I wear grace like my most beautiful jewel.']],
    familie: ['Family together', ['My family is together, healthy and happy.', 'Our home is full of laughter, long dinners and love.', 'We are united, we support and enjoy one another.']]
  },
  fr: {
    calatorii: ['Voyages', ['Le monde est ma galerie : Florence, Paris et Kyoto m’attendent.', 'Je collectionne les couchers de soleil, les belles villes et les souvenirs, pas les objets.', 'Je voyage souvent, confortablement et le cœur ouvert.']],
    succes: ['Réussite', ['Je construis avec discipline une carrière dont je suis fière.', 'Les bonnes opportunités me trouvent parce que je suis prête.', 'Mon travail compte, et mes résultats parlent pour moi.']],
    carti: ['Livres', ['Je lis chaque jour ; chaque livre me rend plus sage.', 'Mon esprit est une bibliothèque choisie avec soin.', 'Vingt pages par jour, une vie entière d’idées.']],
    bani: ['Liberté financière', ['L’argent vient à moi facilement et je l’investis avec sagesse.', 'Je suis libre financièrement et généreuse avec ceux que j’aime.', 'Mon portefeuille grandit, pas à pas, année après année.']],
    masina: ['La voiture de mes rêves', ['Je conduis la voiture de mes rêves, avec élégance et en sécurité.', 'Chaque route est une joie, dans une voiture qui me ressemble.']],
    casa: ['Ma maison', ['Ma maison est lumineuse, chaleureuse et pleine de beauté.', 'J’ai un foyer où la paix et l’amour se sentent dès la porte.', 'La maison de mes rêves devient réalité.']],
    iubire: ['Le vrai amour', ['J’aime et je suis aimée, avec tendresse, respect et loyauté.', 'J’attire un amour sincère, mûr et beau.', 'Mon cœur est ouvert au véritable amour.']],
    credinta: ['Foi et prière', ['J’ai confiance en Dieu et en Son dessein pour moi.', 'Je commence et termine ma journée par la prière et la gratitude.', 'La foi me donne la paix, la force et la lumière.']],
    frumusete: ['Beauté', ['Je prends soin de moi avec amour ; je rayonne de l’intérieur.', 'Je suis belle, lumineuse et en paix avec mon miroir.', 'Mes rituels de soin sont des moments d’amour de soi.']],
    fit: ['En forme et en bonne santé', ['Mon corps est fort, sain et plein d’énergie.', 'Je bouge chaque jour parce que j’aime mon corps.', 'Je mange sainement, je dors bien, je me sens merveilleusement bien.']],
    eleganta: ['Élégance et raffinement', ['Je suis raffinée, féminine et élégante en pensées, en paroles et en gestes.', 'Mon élégance est discrète : la qualité, pas la quantité.', 'Je porte la grâce comme mon plus beau bijou.']],
    familie: ['La famille réunie', ['Ma famille est réunie, en bonne santé et heureuse.', 'Notre maison est pleine de rires, de longs dîners et d’amour.', 'Nous sommes unis, nous nous soutenons et profitons les uns des autres.']]
  },
  es: {
    calatorii: ['Viajes', ['El mundo es mi galería: Florencia, París y Kioto me esperan.', 'Colecciono atardeceres, ciudades bonitas y recuerdos, no cosas.', 'Viajo a menudo, con comodidad y con el corazón abierto.']],
    succes: ['Éxito', ['Construyo con disciplina una carrera de la que me siento orgullosa.', 'Las oportunidades adecuadas me encuentran porque estoy preparada.', 'Mi trabajo importa y mis resultados hablan por mí.']],
    carti: ['Libros', ['Leo cada día; cada libro me hace más sabia.', 'Mi mente es una biblioteca elegida con cuidado.', 'Veinte páginas al día, toda una vida de ideas.']],
    bani: ['Libertad financiera', ['El dinero llega a mí con facilidad y lo invierto con sabiduría.', 'Soy libre financieramente y generosa con mis seres queridos.', 'Mi cartera crece, paso a paso, año tras año.']],
    masina: ['El coche de mis sueños', ['Conduzco el coche de mis sueños, con elegancia y seguridad.', 'Cada camino es una alegría, en un coche que se parece a mí.']],
    casa: ['Mi casa', ['Mi casa es luminosa, cálida y llena de belleza.', 'Tengo un hogar donde la paz y el amor se sienten desde la puerta.', 'La casa de mis sueños se está haciendo realidad.']],
    iubire: ['Amor verdadero', ['Amo y soy amada, con ternura, respeto y lealtad.', 'Atraigo un amor sincero, maduro y hermoso.', 'Mi corazón está abierto al amor verdadero.']],
    credinta: ['Fe y oración', ['Confío en Dios y en Su plan para mí.', 'Empiezo y termino el día con oración y gratitud.', 'La fe me da paz, fuerza y luz.']],
    frumusete: ['Belleza', ['Me cuido con amor; brillo de dentro hacia fuera.', 'Soy bella, luminosa y estoy en paz con el espejo.', 'Mis rituales de cuidado son momentos de amor propio.']],
    fit: ['En forma y saludable', ['Mi cuerpo es fuerte, sano y lleno de energía.', 'Me muevo cada día porque amo mi cuerpo.', 'Como sano, duermo bien y me siento de maravilla.']],
    eleganta: ['Elegancia y refinamiento', ['Soy refinada, femenina y elegante en pensamientos, palabras y gestos.', 'Mi elegancia es serena: calidad, no cantidad.', 'Llevo la gracia como mi joya más bella.']],
    familie: ['La familia unida', ['Mi familia está unida, sana y feliz.', 'Nuestra casa está llena de risas, largas cenas y amor.', 'Estamos unidos, nos apoyamos y disfrutamos unos de otros.']]
  },
  it: {
    calatorii: ['Viaggi', ['Il mondo è la mia galleria: Firenze, Parigi e Kyoto mi aspettano.', 'Colleziono tramonti, città bellissime e ricordi, non oggetti.', 'Viaggio spesso, comodamente e con il cuore aperto.']],
    succes: ['Successo', ['Costruisco con disciplina una carriera di cui sono fiera.', 'Le giuste opportunità mi trovano perché sono pronta.', 'Il mio lavoro conta e i miei risultati parlano per me.']],
    carti: ['Libri', ['Leggo ogni giorno; ogni libro mi rende più saggia.', 'La mia mente è una biblioteca scelta con cura.', 'Venti pagine al giorno, una vita intera di idee.']],
    bani: ['Libertà finanziaria', ['Il denaro arriva a me con facilità e lo investo con saggezza.', 'Sono libera finanziariamente e generosa con chi amo.', 'Il mio portafoglio cresce, passo dopo passo, anno dopo anno.']],
    masina: ['L’auto dei sogni', ['Guido l’auto dei miei sogni, con eleganza e in sicurezza.', 'Ogni strada è una gioia, in un’auto che mi somiglia.']],
    casa: ['La mia casa', ['La mia casa è luminosa, calda e piena di bellezza.', 'Ho una casa in cui pace e amore si sentono già dalla porta.', 'La casa dei miei sogni sta diventando realtà.']],
    iubire: ['Il vero amore', ['Amo e sono amata, con tenerezza, rispetto e lealtà.', 'Attiro un amore sincero, maturo e bello.', 'Il mio cuore è aperto al vero amore.']],
    credinta: ['Fede e preghiera', ['Confido in Dio e nel Suo disegno per me.', 'Comincio e concludo la giornata con preghiera e gratitudine.', 'La fede mi dà pace, forza e luce.']],
    frumusete: ['Bellezza', ['Mi prendo cura di me con amore; risplendo da dentro a fuori.', 'Sono bella, luminosa e in pace con lo specchio.', 'I miei rituali di bellezza sono momenti di amore per me stessa.']],
    fit: ['In forma e in salute', ['Il mio corpo è forte, sano e pieno di energia.', 'Mi muovo ogni giorno perché amo il mio corpo.', 'Mangio sano, dormo bene, mi sento meravigliosamente.']],
    eleganta: ['Eleganza e raffinatezza', ['Sono raffinata, femminile ed elegante nei pensieri, nelle parole e nei gesti.', 'La mia eleganza è discreta: qualità, non quantità.', 'Indosso la grazia come il mio gioiello più bello.']],
    familie: ['La famiglia unita', ['La mia famiglia è unita, sana e felice.', 'La nostra casa è piena di risate, lunghe cene e amore.', 'Siamo uniti, ci sosteniamo e ci godiamo la compagnia gli uni degli altri.']]
  },
  de: {
    calatorii: ['Reisen', ['Die Welt ist meine Galerie: Florenz, Paris und Kyoto warten auf mich.', 'Ich sammle Sonnenuntergänge, schöne Städte und Erinnerungen, keine Dinge.', 'Ich reise oft, bequem und mit offenem Herzen.']],
    succes: ['Erfolg', ['Mit Disziplin baue ich eine Karriere auf, auf die ich stolz bin.', 'Die richtigen Chancen finden mich, weil ich vorbereitet bin.', 'Meine Arbeit zählt, und meine Ergebnisse sprechen für mich.']],
    carti: ['Bücher', ['Ich lese jeden Tag; jedes Buch macht mich weiser.', 'Mein Geist ist eine sorgfältig ausgewählte Bibliothek.', 'Zwanzig Seiten am Tag, ein Leben voller Ideen.']],
    bani: ['Finanzielle Freiheit', ['Geld kommt leicht zu mir, und ich investiere es klug.', 'Ich bin finanziell frei und großzügig zu den Menschen, die ich liebe.', 'Mein Portfolio wächst, Schritt für Schritt, Jahr für Jahr.']],
    masina: ['Traumauto', ['Ich fahre mein Traumauto, elegant und sicher.', 'Jede Fahrt ist eine Freude, in einem Auto, das zu mir passt.']],
    casa: ['Mein Zuhause', ['Mein Zuhause ist hell, warm und voller Schönheit.', 'Ich habe ein Heim, in dem man Frieden und Liebe schon an der Tür spürt.', 'Mein Traumhaus wird Wirklichkeit.']],
    iubire: ['Wahre Liebe', ['Ich liebe und werde geliebt, mit Zärtlichkeit, Respekt und Treue.', 'Ich ziehe eine aufrichtige, reife und schöne Liebe an.', 'Mein Herz ist offen für die wahre Liebe.']],
    credinta: ['Glaube und Gebet', ['Ich vertraue auf Gott und auf Seinen Plan für mich.', 'Ich beginne und beende meinen Tag mit Gebet und Dankbarkeit.', 'Der Glaube schenkt mir Frieden, Kraft und Licht.']],
    frumusete: ['Schönheit', ['Ich pflege mich mit Liebe; ich strahle von innen nach außen.', 'Ich bin schön, strahlend und im Frieden mit dem Spiegel.', 'Meine Pflegerituale sind Momente der Selbstliebe.']],
    fit: ['Fit und gesund', ['Mein Körper ist stark, gesund und voller Energie.', 'Ich bewege mich jeden Tag, weil ich meinen Körper liebe.', 'Ich esse gesund, schlafe gut und fühle mich wunderbar.']],
    eleganta: ['Eleganz und Raffinesse', ['Ich bin kultiviert, feminin und elegant in Gedanken, Worten und Gesten.', 'Meine Eleganz ist leise: Qualität statt Quantität.', 'Ich trage Anmut wie mein schönstes Schmuckstück.']],
    familie: ['Die Familie vereint', ['Meine Familie ist zusammen, gesund und glücklich.', 'Unser Zuhause ist voller Lachen, langer Abendessen und Liebe.', 'Wir halten zusammen, unterstützen einander und genießen unsere Zeit.']]
  }
};

// ---------- citatul zilei din planner și de pe carduri (paralel cu today.js) ----------
const QUOTES = {
  en: [
    ['Discipline is the bridge between goals and accomplishment.', 'Jim Rohn'],
    ['It is not because things are difficult that we do not dare; it is because we do not dare that they are difficult.', 'Seneca'],
    ['Simplicity is the ultimate sophistication.', 'Leonardo da Vinci'],
    ['Quality is not an act, it is a habit.', 'Aristotle'],
    ['Do what you can, with what you have, where you are.', 'Theodore Roosevelt'],
    ['Art does not reproduce the visible; rather, it makes visible.', 'Paul Klee'],
    ['An investment in knowledge pays the best interest.', 'Benjamin Franklin'],
    ['Focus means saying no to the hundred other good ideas.', 'Steve Jobs'],
    ['He who has a why to live can bear almost any how.', 'Friedrich Nietzsche'],
    ['Elegance is the only beauty that never fades.', 'Audrey Hepburn'],
    ['Don’t count the days, make the days count.', 'Muhammad Ali'],
    ['What you do every day matters more than what you do once in a while.', 'Gretchen Rubin'],
    ['Style is a way to say who you are without having to speak.', 'Rachel Zoe'],
    ['The stock market is a device for transferring money from the impatient to the patient.', 'Warren Buffett']
  ],
  fr: [
    ['La discipline est le pont entre les objectifs et leur accomplissement.', 'Jim Rohn'],
    ['Ce n’est pas parce que les choses sont difficiles que nous n’osons pas, c’est parce que nous n’osons pas qu’elles sont difficiles.', 'Sénèque'],
    ['La simplicité est la sophistication suprême.', 'Léonard de Vinci'],
    ['L’excellence n’est pas un acte, mais une habitude.', 'Aristote'],
    ['Fais ce que tu peux, avec ce que tu as, là où tu es.', 'Theodore Roosevelt'],
    ['L’art ne reproduit pas le visible ; il rend visible.', 'Paul Klee'],
    ['Un investissement dans le savoir rapporte les meilleurs intérêts.', 'Benjamin Franklin'],
    ['Se concentrer, c’est dire non à cent autres bonnes idées.', 'Steve Jobs'],
    ['Celui qui a un pourquoi qui lui tient lieu de but peut vivre avec n’importe quel comment.', 'Friedrich Nietzsche'],
    ['L’élégance est la seule beauté qui ne se fane jamais.', 'Audrey Hepburn'],
    ['Ne compte pas les jours, fais que les jours comptent.', 'Muhammad Ali'],
    ['Ce que tu fais chaque jour compte plus que ce que tu fais de temps en temps.', 'Gretchen Rubin'],
    ['Le style est une façon de dire qui tu es sans avoir à parler.', 'Rachel Zoe'],
    ['La Bourse est un mécanisme qui transfère l’argent des impatients vers les patients.', 'Warren Buffett']
  ],
  es: [
    ['La disciplina es el puente entre las metas y los logros.', 'Jim Rohn'],
    ['No es porque las cosas sean difíciles que no nos atrevemos; es porque no nos atrevemos que son difíciles.', 'Séneca'],
    ['La simplicidad es la máxima sofisticación.', 'Leonardo da Vinci'],
    ['La excelencia no es un acto, sino un hábito.', 'Aristóteles'],
    ['Haz lo que puedas, con lo que tengas, donde estés.', 'Theodore Roosevelt'],
    ['El arte no reproduce lo visible, sino que hace visible.', 'Paul Klee'],
    ['Invertir en conocimiento produce siempre los mejores intereses.', 'Benjamin Franklin'],
    ['Concentrarse es decir no a otras cien buenas ideas.', 'Steve Jobs'],
    ['Quien tiene un porqué para vivir puede soportar casi cualquier cómo.', 'Friedrich Nietzsche'],
    ['La elegancia es la única belleza que nunca se marchita.', 'Audrey Hepburn'],
    ['No cuentes los días, haz que los días cuenten.', 'Muhammad Ali'],
    ['Lo que haces cada día importa más que lo que haces de vez en cuando.', 'Gretchen Rubin'],
    ['El estilo es una forma de decir quién eres sin tener que hablar.', 'Rachel Zoe'],
    ['La bolsa es un mecanismo para transferir dinero de los impacientes a los pacientes.', 'Warren Buffett']
  ],
  it: [
    ['La disciplina è il ponte tra gli obiettivi e i risultati.', 'Jim Rohn'],
    ['Non è perché le cose sono difficili che non osiamo; è perché non osiamo che sono difficili.', 'Seneca'],
    ['La semplicità è la suprema sofisticazione.', 'Leonardo da Vinci'],
    ['L’eccellenza non è un atto, ma un’abitudine.', 'Aristotele'],
    ['Fai quello che puoi, con quello che hai, dove sei.', 'Theodore Roosevelt'],
    ['L’arte non riproduce ciò che è visibile, ma rende visibile ciò che non sempre lo è.', 'Paul Klee'],
    ['Un investimento in conoscenza paga sempre il miglior interesse.', 'Benjamin Franklin'],
    ['Concentrarsi significa dire di no a cento altre buone idee.', 'Steve Jobs'],
    ['Chi ha un perché per vivere può sopportare quasi ogni come.', 'Friedrich Nietzsche'],
    ['L’eleganza è l’unica bellezza che non sfiorisce mai.', 'Audrey Hepburn'],
    ['Non contare i giorni, fai in modo che i giorni contino.', 'Muhammad Ali'],
    ['Ciò che fai ogni giorno conta più di ciò che fai ogni tanto.', 'Gretchen Rubin'],
    ['Lo stile è un modo per dire chi sei senza dover parlare.', 'Rachel Zoe'],
    ['La Borsa è uno strumento per trasferire denaro dagli impazienti ai pazienti.', 'Warren Buffett']
  ],
  de: [
    ['Disziplin ist die Brücke zwischen Zielen und Erfolgen.', 'Jim Rohn'],
    ['Nicht weil es schwer ist, wagen wir es nicht, sondern weil wir es nicht wagen, ist es schwer.', 'Seneca'],
    ['Einfachheit ist die höchste Stufe der Vollendung.', 'Leonardo da Vinci'],
    ['Exzellenz ist keine Handlung, sondern eine Gewohnheit.', 'Aristoteles'],
    ['Tu, was du kannst, mit dem, was du hast, dort, wo du bist.', 'Theodore Roosevelt'],
    ['Kunst gibt nicht das Sichtbare wieder, sondern macht sichtbar.', 'Paul Klee'],
    ['Eine Investition in Wissen bringt immer noch die besten Zinsen.', 'Benjamin Franklin'],
    ['Fokussieren heißt, Nein zu hundert anderen guten Ideen zu sagen.', 'Steve Jobs'],
    ['Wer ein Warum zum Leben hat, erträgt fast jedes Wie.', 'Friedrich Nietzsche'],
    ['Eleganz ist die einzige Schönheit, die nie vergeht.', 'Audrey Hepburn'],
    ['Zähle nicht die Tage, sondern mach, dass die Tage zählen.', 'Muhammad Ali'],
    ['Was du jeden Tag tust, zählt mehr als das, was du ab und zu tust.', 'Gretchen Rubin'],
    ['Stil ist eine Art zu sagen, wer du bist, ohne sprechen zu müssen.', 'Rachel Zoe'],
    ['Die Börse ist ein Mechanismus, der Geld von den Ungeduldigen zu den Geduldigen transferiert.', 'Warren Buffett']
  ]
};

function dayIndex(k) {
  const [y, m, d] = k.split('-').map(Number);
  return Math.floor(Date.UTC(y, m - 1, d) / 86400000);
}

function chosen() {
  const s = store.get().settings;
  const l = (s.quoteLangs || [s.uiLang || 'en']).filter(x => LANGS.includes(x));
  return l.length ? l : ['ro'];
}

// Cu mai multe limbi alese, alternează zilnic (decalat față de tipul mantrei, ca să nu cadă
// mereu același tip pe aceeași limbă).
function langFor(k) {
  const l = chosen();
  const d = dayIndex(k);
  return l[(d + Math.floor(d / 6)) % l.length];
}

module.exports = { LANGS, NAMES, AI_NAMES, META, LIBRARY, AREAS, QUOTES, langFor, chosen };
