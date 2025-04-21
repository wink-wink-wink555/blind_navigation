# Tactile Paving Navigation Assistant System

This is a Flask and YOLO model-based tactile paving navigation assistant system designed to help visually impaired people identify tactile paving and provide voice guidance.

## Project Introduction

The Tactile Paving Navigation Assistant System is an innovative application combining computer vision and artificial intelligence, specially designed for the visually impaired. The system identifies changes in tactile paving direction through real-time video analysis technology and guides visually impaired people to walk correctly along the tactile paving through voice prompts. At the same time, the system also provides location sharing functionality, allowing family members to know the location of visually impaired people at any time, improving travel safety.

This project uses the YOLO (You Only Look Once) object detection algorithm, combined with a self-collected and annotated tactile paving dataset for training, which can accurately identify tactile paving and judge its extension direction. Through speech synthesis technology, the system conveys navigation information to users in a natural and friendly way.

## Problems Solved

This system mainly solves the following problems:

1. **Tactile Paving Recognition and Navigation**: Through real-time video analysis, it identifies the position and direction changes of tactile paving, helping visually impaired people walk safely along the tactile paving.

2. **Real-time Voice Feedback**: When a change in tactile paving direction is detected, it automatically provides voice prompts, allowing visually impaired people to adjust their direction of travel in a timely manner.

3. **Safety Monitoring**: Through the location sharing function, family members can remotely monitor the location of visually impaired people and provide help when needed.

4. **Personalized Experience**: Provides customization of voice speed, volume, and other parameters to meet the needs of different users.

5. **Digital Divide**: Reduces barriers for visually impaired people to use modern urban facilities, improving self-care ability and travel convenience.

## Feature Highlights

- Real-time Video Analysis: Uses YOLO model to identify tactile paving in real-time
- Voice Feedback: Provides real-time voice prompts
- User System: Includes registration, login, and password recovery functions
- Location Sharing: Supports location sharing, making it convenient for family members to know the location of visually impaired people
- User Settings: Customizable voice speed, volume, and other parameters

## Installation Requirements

- Python 3.8+
- MySQL database
- Necessary Python libraries (see requirements.txt)

## Installation Steps

1. Clone the repository to your local machine:
```bash
git clone https://github.com/wink-wink-wink555/blind-navigation.git
cd blind-navigation
```

2. Create and activate a virtual environment (optional but recommended):
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Download the YOLO model and place it in the models directory:
```bash
# If you already have a trained model, please rename it to best.pt and place it in the models directory
mkdir -p models
# Copy your model file to models/best.pt
```

5. Set up the database:
   - Create MySQL database: blind_navigation
   - The application will automatically create the required tables when it is first run

6. Modify the configuration:
   - Update the database configuration (DB_CONFIG) in app.py
   - Update the email sending configuration (EMAIL_CONFIG)

## Running the Application

```bash
python app.py
```

The application will run at http://127.0.0.1:5000/.

## Usage Instructions

1. Register/Login: You need to register an account for first-time use
2. Upload Video: You can upload a video file for analysis or use the camera for real-time analysis
3. Set Parameters: Adjust voice prompt parameters according to personal needs
4. Location Sharing: Share location with family members

## User Guide

### 1. Account Management

#### Register an Account
1. Visit the system home page and click the "Register" button
2. Fill in username, password, email, and other information
3. Click the "Get Verification Code" button, and the system will send a verification code to your email
4. Enter the received verification code to complete registration

#### Login to the System
1. Enter your username and password
2. Click the "Login" button to enter the system
3. If you forget your password, you can click "Forgot Password" to reset it

### 2. Tactile Paving Navigation

#### Video Analysis
1. Click the "Upload Video" button and select the video file to be analyzed
2. The system will automatically start analyzing the tactile paving in the video
3. When a change in tactile paving direction is detected, the system will automatically play a voice prompt

#### Real-time Navigation
1. Fix your mobile phone or tablet device in an appropriate position to ensure that the camera can capture the tactile paving in front
2. Click the "Start Navigation" button
3. The system will analyze the camera image in real-time and provide voice navigation guidance

### 3. Location Sharing

#### Share Location
1. Click the "Location Sharing" button on the main interface
2. Authorize the system to access location information
3. Select the family member account with which you want to share your location
4. Click the "Start Sharing" button

#### View Location
1. Login to the system with a family member account
2. Click the "View Location" button on the main interface
3. The system will display a map interface, marking the real-time location of the visually impaired person

### 4. System Settings

#### Voice Settings
1. Click the "Settings" button on the main interface
2. Adjust voice speed, volume, and other parameters
3. Click the "Test Voice" button to preview the effect
4. Click the "Save Settings" button to save the changes

## Notes

- This system needs to configure email to support the verification code function
- The model recognition effect depends on the quality of the training data
- Please ensure that camera permissions are enabled (when using the camera)
- The location sharing function requires GPS permissions

## Contact Information

- **Email**: yfsun.jeff@qq.com
- **GitHub**: [wink-wink-wink555](https://github.com/wink-wink-wink555)
- **LinkedIn**: [Yifei Sun](https://www.linkedin.com/in/yifei-sun-0bab66341/)

## Special Thanks

Special thanks to the following members for helping with the collection of tactile paving datasets and participating in annotation and training work:
- Chen Xingyu
- Wang youyi
- Liu Yiheng
- Cai Yuxin

## License

This project is licensed under the [MIT License](LICENSE).

Copyright (c) 2023 Sun Yifei and contributors

This means you are free to use, modify, and distribute this software, whether for personal or commercial purposes, provided that the above copyright notice and permission notice are included in all copies.

For detailed terms, please refer to the [LICENSE](LICENSE) file. 
