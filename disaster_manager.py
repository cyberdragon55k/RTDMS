import mysql.connector
from typing import Dict, List, Any, Optional
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib
import os

class DisasterManager:
    def __init__(self):
        self.setup_database()
        self.setup_predictor()
        
    def setup_database(self):
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': 'root',
            'database': 'disaster'
        }
        self.setup_logging()
        self.initialize_connection()
        self.setup_tables()
    
    def setup_predictor(self):
        self.vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
        self.classifier = RandomForestClassifier(n_estimators=100, random_state=42)
        self.label_encoder = LabelEncoder()
        self.model_path = 'models/severity_model.joblib'
        self.vectorizer_path = 'models/vectorizer.joblib'
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def initialize_connection(self):
        try:
            self.connection = mysql.connector.connect(**self.db_config)
            self.logger.info('Database connection initialized successfully')
        except mysql.connector.Error as err:
            self.logger.error(f'Error initializing connection: {err}')
            raise

    def get_connection(self):
        if not self.connection or not self.connection.is_connected():
            self.initialize_connection()
        return self.connection

    def setup_tables(self):
        connection = self.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS disasters (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    type TEXT,
                    location TEXT,
                    severity TEXT,
                    date TEXT,
                    description TEXT,
                    source TEXT,
                    confidence FLOAT
                )
            """)
            connection.commit()
            self.logger.info('Database tables created successfully')
        except mysql.connector.Error as err:
            self.logger.error(f'Error setting up database: {err}')
            raise
        finally:
            cursor.close()

    def get_training_data(self) -> tuple:
        connection = self.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT description, severity 
                FROM disasters 
                WHERE severity IS NOT NULL
            """)
            data = cursor.fetchall()
            
            if not data:
                return None, None
                
            descriptions = [row[0] for row in data]
            severities = [row[1] for row in data]
            
            return descriptions, severities
        except mysql.connector.Error as err:
            self.logger.error(f'Error fetching training data: {err}')
            return None, None
        finally:
            cursor.close()

    def train(self) -> bool:
        try:
            descriptions, severities = self.get_training_data()
            
            if descriptions is None or len(descriptions) == 0:
                self.logger.warning("No training data available")
                return False
            
            X = self.vectorizer.fit_transform(descriptions)
            y = self.label_encoder.fit_transform(severities)
            
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            self.classifier.fit(X_train, y_train)
            
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            
            joblib.dump(self.classifier, self.model_path)
            joblib.dump(self.vectorizer, self.vectorizer_path)
            
            train_score = self.classifier.score(X_train, y_train)
            test_score = self.classifier.score(X_test, y_test)
            
            self.logger.info(f"Training accuracy: {train_score:.2f}")
            self.logger.info(f"Testing accuracy: {test_score:.2f}")
            
            return True
        except Exception as e:
            self.logger.error(f"Error during training: {str(e)}")
            return False

    def predict_severity(self, description: str) -> Dict[str, Any]:
        X = self.vectorizer.transform([description])
        severity_encoded = self.classifier.predict(X)[0]
        severity = self.label_encoder.inverse_transform([severity_encoded])[0]
        proba = np.max(self.classifier.predict_proba(X)[0])
        
        return {
            'severity': severity,
            'confidence': float(proba)
        }

    def update_database_severities(self) -> None:
        connection = self.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT id, description 
                FROM disasters 
                WHERE severity IS NULL
            """)
            
            disasters = cursor.fetchall()
            
            for disaster_id, description in disasters:
                if description:
                    prediction = self.predict_severity(description)
                    
                    cursor.execute("""
                        UPDATE disasters 
                        SET severity = %s, confidence = %s 
                        WHERE id = %s
                    """, (prediction['severity'], prediction['confidence'], disaster_id))
            
            connection.commit()
            self.logger.info('Updated database with severity predictions')
        except mysql.connector.Error as err:
            self.logger.error(f'Error updating severities: {err}')
            connection.rollback()
        finally:
            cursor.close()

    def insert_disaster(self, disaster_data: Dict[str, Any]) -> bool:
        query = """
            INSERT INTO disasters 
            (type, location, severity, date, description, source)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self._execute_query(
            query,
            (disaster_data['type'], disaster_data['location'],
             disaster_data['severity'], disaster_data['date'],
             disaster_data['description'], disaster_data['source'])
        )

    def get_all_disasters(self) -> List[tuple]:
        query = "SELECT * FROM disasters"
        return self._fetch_all(query)

    def get_disaster_by_id(self, disaster_id: int) -> Optional[tuple]:
        query = "SELECT * FROM disasters WHERE id = %s"
        result = self._fetch_all(query, (disaster_id,))
        return result[0] if result else None

    def update_disaster(self, disaster_id: int, disaster_data: Dict[str, Any]) -> bool:
        query = """
            UPDATE disasters
            SET type = %s, location = %s, severity = %s,
                date = %s, description = %s, source = %s
            WHERE id = %s
        """
        return self._execute_query(
            query,
            (disaster_data['type'], disaster_data['location'],
             disaster_data['severity'], disaster_data['date'],
             disaster_data['description'], disaster_data['source'],
             disaster_id)
        )

    def delete_disaster(self, disaster_id: int) -> bool:
        query = "DELETE FROM disasters WHERE id = %s"
        return self._execute_query(query, (disaster_id,))

    def _execute_query(self, query: str, params: tuple = None) -> bool:
        connection = self.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            connection.commit()
            return True
        except mysql.connector.Error as err:
            self.logger.error(f'Error executing query: {err}')
            connection.rollback()
            return False
        finally:
            cursor.close()

    def _fetch_all(self, query: str, params: tuple = None) -> List[tuple]:
        connection = self.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        except mysql.connector.Error as err:
            self.logger.error(f'Error fetching data: {err}')
            return []
        finally:
            cursor.close()

    def close(self):
        if self.connection:
            self.connection.close()
            self.logger.info('Database connection closed')

def main():
    manager = DisasterManager()
    

    print("Training severity prediction model...")
    if manager.train():
        print("\nUpdating database with severity predictions...")
        manager.update_database_severities()
        print("Done!")
    
    manager.close()

if __name__ == "__main__":
    main()