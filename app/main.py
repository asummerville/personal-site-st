import streamlit as st
import pandas as pd


st.write('''

# **Alden Summerville**

''')


# st.sidebar.image("https://media-exp1.licdn.com/dms/image/C4E03AQFFmDulax2JMA/profile-displayphoto-shrink_400_400/0/1621271708730?e=1634774400&v=beta&t=v2Q8mRRFxuE0JXjDpkIzySxHh8egmN5SN2MQQ5bHegQ", use_column_width="auto")
st.sidebar.image('img/headshot-circle.png', use_column_width="auto")

st.sidebar.write(''' 

# **About Me**

**University of Virginia Class of 2022**

**B.S. Civil Engineering** - Environmental and Water Resources

**Data Science Minor**

# **Contact Info**

asummerville112@gmail.com

(703)-946-2601

[LinkedIn](https://www.linkedin.com/in/alden-summerville/)



''')


st.write(''' 

## **Hello!**

I am a fourth year student at the University of Virginia studying Civil Engineering focusing in Environmental and Water Resources Engineering with a minor in Data Science. I’m excited to apply my engineering background to critical environmental problems that require technical acumen and creativity. I also have a strong interest in applying my digital skillset to engineering challenges in the built environment as cities undergo rapid digitalization. Please do not hesitate to reach out with any questions!

''')

st.image("img/interests.png", use_column_width="auto")

st.write('''

## **Skills/Tools**

''')

#visualization that shows proficiency of each skill - maybe multiple for each type

st.write('''

## **Projects**

### Arup (Advanced Digital Engineering) *Summer '21 Internship*

-Developed a map-based “Client Insight” web app that consolidates and allows the editing of project information – deployed as a static website with AWS S3

**Tools**: ArcGIS Experience Builder, JavaScript, S3, ArcGIS Pro, ArcGIS Online

-Scripted a python geospatial analysis tool and deployed the tool as a Streamlit web app hosted on AWS EC2 to provide a simple frontend for the client

**Tool**s: Python, ArcPy, ArcGIS Pro, Streamlit, EC2

-Refactored and classed out a JavaScript-based web app and hosted the app with AWS S3, automating deployments with GitHub Actions – added a simple ReactJS element to improve functionality

**Tools**: JavaScript, HTML, CSS, React, S3, GitHub Actions

-Calculated incoming solar radiation on 82 NY Public Library buildings by developing a model in ArcGIS Pro that decreased computation time from days to 4 hours

**Tools**: ArcGIS Pro, Solar Radiation Toolbox, Model Builder (ArcGIS Pro)

### Environmental Resilience Institute (ERI) *Undergraduate Research Assistamt*

-Assisted a multidisciplinary team in researching the spatial and temporal coverage of ~6 million U.S. water quality data points

-Performed statistical analyses and created geospatial visualizations with R, integrating contributions using Git/GitHub

**Tools/Skills**: R, Statistical Analysis (linear and multiple regression), Geospatial Visualization, Github

''')

st.image("img/poster.png", width=800)


st.write('''


## **School Work**

DS 4001 (Machine Learning) [Portfolio]('https://rpubs.com/asummerville11')


''')

st.write('''

## **Personal Interests**

''')