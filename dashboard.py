import statistics
import streamlit as st
import matplotlib.pyplot as plt
from scipy import stats

#Dashboard title
st.title("AgriTrial Nitrate Analysis Dashboard")
st.write("Comparing control and Treatment B)")

#Example nitrate data
control = [10, 12, 11, 13, 9]
treatment_b = [15, 16, 14, 17, 13]

#Calculate means
control_mean = statistics.mean(control)
treatment_b_mean = statistics.mean(treatment_b)

#Calculate 95% confidence intervals
control_ci = stats.t.interval(0.95, df=len(control)-1, loc=control_mean, scale=stats.sem(control))
treatment_b_ci = stats.t.interval(0.95, df=len(treatment_b)-1, loc=treatment_b_mean, scale=stats.sem(treatment_b))

#Display mean values
col1, col2 = st.columns(2)

col1.metric("Control Mean", round(control_mean, 2))
col2.metric("Treatment B Mean", round(treatment_b_mean, 2))

#Display confidence intervals
st.subheader("95% Confidence Intervals")
st.write(f"Control: {control_ci[0]:.2f} - {control_ci[1]:.2f}")
st.write(f"Treatment B: {treatment_b_ci[0]:.2f} - {treatment_b_ci[1]:.2f}")

#Create bar chart with confidence intervals
means = [control_mean, treatment_b_mean]

lower_errors = [control_mean - control_ci[0], treatment_b_mean - treatment_b_ci[0]]
upper_errors = [control_ci[1] - control_mean, treatment_b_ci[1] - treatment_b_mean]

fig, ax = plt.subplots()
ax.bar(["Control", "Treatment B"], means, yerr=[lower_errors, upper_errors], capsize=6)

ax.set_title("Mean Nitrate Levels with 95% Confidence Intervals")
ax.set_xlabel("Treatment Group")
ax.set_ylabel("Mean Nitrate Level")

st.pyplot(fig)

#Interpretation
st.subheader("Interpretation")

difference = treatment_b_mean - control_mean

st.write(f"Treatment B has a mean nitrate level"
         f"{difference:.2f} units higher than Control.")