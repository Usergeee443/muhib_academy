-- Ma'lumotlar bazasini yaratish
CREATE DATABASE IF NOT EXISTS muhib_academy CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE muhib_academy;

-- Kurslar jadvali
CREATE TABLE kurslar (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nom VARCHAR(255) NOT NULL,
    tafsif TEXT,
    davomiyligi VARCHAR(100),
    darslar_soni INT,
    narx DECIMAL(10,2),
    rasm_url VARCHAR(500),
    active BOOLEAN DEFAULT TRUE,
    yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    yangilangan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Namuna ma'lumotlar qo'shish
INSERT INTO kurslar (nom, tafsif, davomiyligi, darslar_soni, narx, rasm_url) VALUES
(
    'Python Backend Development',
    'Python tilida professional backend dasturlash. Django va Flask frameworklari, REST API yaratish, ma\'lumotlar bazasi bilan ishlash, deployment va boshqa zamonaviy texnologiyalar. Kurs davomida real loyihalar ustida ishlab, to\'liq backend dasturchi bo\'lib chiqasiz.',
    '4 oy',
    32,
    1500000,
    'https://images.unsplash.com/photo-1526379095098-d400fd0bf935?w=500&h=300&fit=crop'
),
(
    'JavaScript Full Stack',
    'JavaScript tilida frontend va backend dasturlash. React, Node.js, Express, MongoDB texnologiyalari. Zamonaviy web dasturlash usullari va amaliy loyihalar. SPA (Single Page Application) yaratish va modern development tools.',
    '5 oy',
    40,
    1800000,
    'https://images.unsplash.com/photo-1579468118864-1b9ea3c0db4a?w=500&h=300&fit=crop'
),
(
    'React Frontend Development',
    'React.js kutubxonasi bilan zamonaviy frontend dasturlash. Component-based development, hooks, state management, routing va boshqalar. Redux, Context API, styled-components va boshqa mashhur kutubxonalar bilan ishlash.',
    '3 oy',
    24,
    1200000,
    'https://images.unsplash.com/photo-1633356122544-f134324a6cee?w=500&h=300&fit=crop'
),
(
    'Mobile Development (Flutter)',
    'Flutter framework yordamida Android va iOS uchun mobile ilovalar yaratish. Dart tili, widget-lar bilan ishlash, state management, REST API integration, va app store\'ga publish qilish jarayoni.',
    '4 oy',
    36,
    1600000,
    'https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=500&h=300&fit=crop'
),
(
    'UI/UX Design',
    'Foydalanuvchi interfeysi va tajribasi dizayni. Figma, Adobe XD, Sketch dasturlarida ishlash. Design thinking, user research, wireframing, prototyping va usability testing. Modern design principles va trends.',
    '3 oy',
    28,
    1000000,
    'https://images.unsplash.com/photo-1561070791-2526d30994b5?w=500&h=300&fit=crop'
),
(
    'Data Science va Machine Learning',
    'Python tilida ma\'lumotlar tahlili va mashina o\'rganishi. Pandas, NumPy, Matplotlib, Scikit-learn, TensorFlow kutubxonalari. Data preprocessing, visualization, ML algoritmlar va real loyihalar ustida amaliy ishlash.',
    '6 oy',
    48,
    2000000,
    'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=500&h=300&fit=crop'
);

-- Indeks qo'shish (tezlik uchun)
CREATE INDEX idx_kurslar_active ON kurslar(active);