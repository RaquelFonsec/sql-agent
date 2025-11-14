import pytest

class MockValidator:
    def validate(self, sql):
        sql_upper = sql.upper()
        dangerous = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE']
        
        is_valid = True
        errors = []
        
        for word in dangerous:
            if word in sql_upper:
                is_valid = False
                errors.append(f"Operacao perigosa: {word}")
        
        return {'is_valid': is_valid, 'errors': errors}

class TestSQLValidator:
    
    def test_valid_select_query(self):
        validator = MockValidator()
        sql = "SELECT * FROM clientes;"
        
        result = validator.validate(sql)
        
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
    
    def test_block_drop_query(self):
        validator = MockValidator()
        sql = "DROP TABLE clientes;"
        
        result = validator.validate(sql)
        
        assert result['is_valid'] is False
        assert 'DROP' in str(result['errors'])
    
    def test_block_delete_query(self):
        validator = MockValidator()
        sql = "DELETE FROM clientes WHERE id=1;"
        
        result = validator.validate(sql)
        
        assert result['is_valid'] is False
        assert 'DELETE' in str(result['errors'])
    
    def test_block_update_query(self):
        validator = MockValidator()
        sql = "UPDATE clientes SET saldo=0;"
        
        result = validator.validate(sql)
        
        assert result['is_valid'] is False
    
    @pytest.mark.parametrize("dangerous_word", [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"
    ])
    def test_block_all_dangerous_operations(self, dangerous_word):
        validator = MockValidator()
        sql = f"{dangerous_word} TABLE clientes;"
        
        result = validator.validate(sql)
        
        assert result['is_valid'] is False
    
    def test_case_insensitive_validation(self):
        validator = MockValidator()
        sql = "drop table clientes;"
        
        result = validator.validate(sql)
        
        assert result['is_valid'] is False
