-- Insert payment record with ID 1
INSERT INTO payments (
    id,
    payment_id, 
    parent_id, 
    child_id, 
    amount, 
    currency, 
    status, 
    payment_method, 
    description, 
    journey_date, 
    created_at
) VALUES (
    1,
    'PAY_1755022000_0001', 
    '1', 
    '1', 
    500.00, 
    'GHS', 
    'pending', 
    'online', 
    'School Fees - First Term 2024', 
    '2024-02-15', 
    NOW()
);

-- Verify the insertion
SELECT * FROM payments WHERE id = 1; 