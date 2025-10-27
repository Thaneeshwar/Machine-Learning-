from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import json
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)
CORS(app)

class CarPricePredictor:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.feature_names = []
        
    def preprocess_data(self, df):
        """Preprocess the car data for training"""
        # Create a copy to avoid modifying original data
        data = df.copy()
        
        # Handle missing values
        numeric_columns = ['Year', 'Kilometers_Driven', 'Mileage', 'Engine', 'Power', 'Seats']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
                data[col].fillna(data[col].median(), inplace=True)
        
        # Create car age feature
        current_year = pd.Timestamp.now().year
        data['Car_Age'] = current_year - data['Year']
        
        # Extract brand from name
        data['Brand'] = data['Name'].str.split().str[0]
        
        # Encode categorical variables
        categorical_columns = ['Fuel_Type', 'Transmission', 'Owner_Type', 'Location', 'Brand']
        for col in categorical_columns:
            if col in data.columns:
                self.label_encoders[col] = LabelEncoder()
                data[col] = self.label_encoders[col].fit_transform(data[col].astype(str))
        
        # Select features for training
        feature_columns = ['Car_Age', 'Kilometers_Driven', 'Mileage', 'Engine', 'Power', 
                          'Seats', 'Fuel_Type', 'Transmission', 'Owner_Type', 'Location', 'Brand']
        
        # Keep only columns that exist in data
        available_features = [col for col in feature_columns if col in data.columns]
        self.feature_names = available_features
        
        return data[available_features], data['Price']
    
    def train_model(self, X, y):
        """Train the Random Forest model"""
        # Split the data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale the features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train the model
        self.model.fit(X_train_scaled, y_train)
        
        # Make predictions
        y_pred = self.model.predict(X_test_scaled)
        
        # Calculate metrics
        metrics = {
            'r2': r2_score(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'mae': mean_absolute_error(y_test, y_pred),
            'mape': np.mean(np.abs((y_test - y_pred) / y_test)) * 100
        }
        
        return metrics, y_test, y_pred
    
    def get_feature_importance(self):
        """Get feature importance from the trained model"""
        if hasattr(self.model, 'feature_importances_'):
            importance_df = pd.DataFrame({
                'feature': self.feature_names,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            return importance_df.to_dict('records')
        return []
    
    def create_visualizations(self, X, y, y_test, y_pred):
        """Create visualization charts"""
        charts = {}
        
        try:
            # Feature Importance Plot
            plt.figure(figsize=(10, 6))
            feature_importance = self.get_feature_importance()
            features = [item['feature'] for item in feature_importance[:10]]
            importances = [item['importance'] for item in feature_importance[:10]]
            
            plt.barh(features, importances)
            plt.xlabel('Feature Importance')
            plt.title('Top 10 Feature Importance')
            plt.tight_layout()
            
            # Convert to base64
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight')
            img_buffer.seek(0)
            charts['feature_importance'] = base64.b64encode(img_buffer.getvalue()).decode()
            plt.close()
            
            # Price Distribution
            plt.figure(figsize=(10, 6))
            plt.hist(y, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            plt.xlabel('Price (₹)')
            plt.ylabel('Frequency')
            plt.title('Car Price Distribution')
            plt.tight_layout()
            
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight')
            img_buffer.seek(0)
            charts['price_distribution'] = base64.b64encode(img_buffer.getvalue()).decode()
            plt.close()
            
            # Actual vs Predicted
            plt.figure(figsize=(8, 6))
            plt.scatter(y_test, y_pred, alpha=0.6)
            plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
            plt.xlabel('Actual Price')
            plt.ylabel('Predicted Price')
            plt.title('Actual vs Predicted Prices')
            plt.tight_layout()
            
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight')
            img_buffer.seek(0)
            charts['prediction_plot'] = base64.b64encode(img_buffer.getvalue()).decode()
            plt.close()
            
        except Exception as e:
            print(f"Error creating visualizations: {e}")
        
        return charts

@app.route('/api/analyze', methods=['POST'])
def analyze_car_data():
    try:
        # Get data from request
        data = request.get_json()
        if not data or 'cars' not in data:
            return jsonify({'error': 'No car data provided'}), 400
        
        # Convert to DataFrame
        df = pd.DataFrame(data['cars'])
        
        # Initialize predictor
        predictor = CarPricePredictor()
        
        # Preprocess data
        X, y = predictor.preprocess_data(df)
        
        # Train model
        metrics, y_test, y_pred = predictor.train_model(X, y)
        
        # Get feature importance
        feature_importance = predictor.get_feature_importance()
        
        # Create sample predictions
        sample_predictions = []
        for i in range(min(15, len(y_test))):
            sample_predictions.append({
                'name': df.iloc[i]['Name'] if 'Name' in df.columns else f'Car {i+1}',
                'actual': int(y_test.iloc[i]),
                'predicted': int(y_pred[i]),
                'error': int(y_pred[i] - y_test.iloc[i]),
                'errorPercentage': float(np.abs((y_pred[i] - y_test.iloc[i]) / y_test.iloc[i]) * 100)
            })
        
        # Create visualizations
        charts = predictor.create_visualizations(X, y, y_test, y_pred)
        
        # Prepare response
        response = {
            'summary': {
                'totalCars': len(df),
                'avgPrice': int(y.mean()),
                'minPrice': int(y.min()),
                'maxPrice': int(y.max()),
                'accuracy': float(100 - metrics['mape'])
            },
            'metrics': metrics,
            'features': feature_importance,
            'predictions': sample_predictions,
            'charts': charts
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sample-data', methods=['GET'])
def get_sample_data():
    """Generate sample car data for testing"""
    np.random.seed(42)
    
    brands = ['Maruti Suzuki', 'Hyundai', 'Honda', 'Toyota', 'Ford', 'BMW', 'Mercedes', 'Audi']
    models = ['Swift', 'i20', 'City', 'Innova', 'EcoSport', 'X1', 'C-Class', 'A4']
    locations = ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Kolkata']
    fuel_types = ['Petrol', 'Diesel', 'CNG']
    
    sample_data = []
    current_year = 2024
    
    for i in range(100):
        brand = np.random.choice(brands)
        model = np.random.choice(models)
        year = current_year - np.random.randint(1, 10)
        
        # Base price based on brand
        if brand in ['BMW', 'Mercedes', 'Audi']:
            base_price = 1_800_000
        elif brand in ['Toyota', 'Honda']:
            base_price = 900_000
        else:
            base_price = 600_000
        
        # Adjust price based on age and random factors
        age = current_year - year
        price = base_price * (0.85 ** age) * np.random.uniform(0.8, 1.2)
        
        car = {
            'Name': f'{brand} {model}',
            'Location': np.random.choice(locations),
            'Year': year,
            'Kilometers_Driven': np.random.randint(10000, 80000),
            'Fuel_Type': np.random.choice(fuel_types),
            'Transmission': np.random.choice(['Manual', 'Automatic']),
            'Owner_Type': np.random.choice(['First', 'Second']),
            'Mileage': round(np.random.uniform(12, 20), 1),
            'Engine': np.random.choice([1197, 1498, 1598, 1995, 2143]),
            'Power': np.random.randint(70, 200),
            'Seats': np.random.choice([5, 7]),
            'Price': int(price)
        }
        sample_data.append(car)
    
    return jsonify({'cars': sample_data})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
