CREATE DATABASE IF NOT EXISTS my_datawarehouse
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE my_datawarehouse;

CREATE TABLE IF NOT EXISTS reviews (
    review_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    review_text TEXT NOT NULL,
    sentiment VARCHAR(20) DEFAULT NULL,
    keywords JSON DEFAULT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO reviews (user_id, review_text, sentiment, keywords, status) VALUES
('user_001', '배송이 정말 빨랐고 포장도 깔끔해서 만족합니다.', NULL, NULL, 'pending'),
('user_002', '생각보다 품질이 별로였고 마감이 아쉬웠어요.', NULL, NULL, 'pending'),
('user_003', '가격 대비 성능이 좋아서 재구매 의사 있습니다.', NULL, NULL, 'pending'),
('user_004', '화면 색감이 선명하고 배터리도 오래가네요.', NULL, NULL, 'pending'),
('user_005', '설명서가 부족해서 설치에 시간이 오래 걸렸습니다.', NULL, NULL, 'pending'),
('user_006', '사이즈가 딱 맞고 착용감이 편안합니다.', NULL, NULL, 'pending'),
('user_007', '소음이 생각보다 커서 밤에는 사용하기 어렵네요.', NULL, NULL, 'pending'),
('user_008', '고객센터 응답이 빨라서 문제를 바로 해결했어요.', NULL, NULL, 'pending'),
('user_009', '처음에는 좋았는데 일주일 만에 고장이 났습니다.', NULL, NULL, 'pending'),
('user_010', '디자인이 예쁘고 기능도 직관적이라 만족해요.', NULL, NULL, 'pending'),
('user_011', '배송 지연이 길어서 선물 일정에 맞추지 못했어요.', NULL, NULL, 'pending'),
('user_012', '성능은 무난하지만 기대했던 만큼은 아니었습니다.', NULL, NULL, 'pending'),
('user_013', '재질이 튼튼하고 오염도 잘 닦여서 좋아요.', NULL, NULL, 'pending'),
('user_014', '앱 연동이 자주 끊겨서 사용성이 떨어집니다.', NULL, NULL, 'pending'),
('user_015', '친절한 안내 덕분에 설치를 쉽게 끝냈습니다.', NULL, NULL, 'pending'),
('user_016', '색상이 사진과 달라서 조금 실망했습니다.', NULL, NULL, 'pending'),
('user_017', '배송은 느렸지만 제품 자체는 만족스럽습니다.', NULL, NULL, 'pending'),
('user_018', '버튼 반응이 느리고 인터페이스가 불편해요.', NULL, NULL, 'pending'),
('user_019', '가격은 조금 비싸지만 품질은 확실히 좋네요.', NULL, NULL, 'pending'),
('user_020', '교환 처리 과정이 복잡해서 불편했습니다.', NULL, NULL, 'pending');
