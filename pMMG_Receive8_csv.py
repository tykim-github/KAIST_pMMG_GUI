import serial
import csv
import matplotlib.pyplot as plt
import pandas as pd

# Use LaTeX font 
# plt.rc('text', usetex=True)
plt.rc('font', family='serif')



# 장치 관리자에서 COM포트 번호 확인하기
serialPort = serial.Serial('COM10', 921600, timeout=1)

# CSV 파일 열기 (기록할 파일 경로) (실험마다 파일명 꼭 바꾸기!!)
csv_filename = 'dataFile8.csv'

# 전체 코드
with open(csv_filename, mode='w', newline='') as file:
    writer = csv.writer(file)
    
    # CSV 파일의 헤더 추가
    writer.writerow(['Time[ms]', 'Pressure1[kPa]', 'Pressure2[kPa]', 'Pressure3[kPa]', 'Pressure4[kPa]', 'Pressure5[kPa]', 'Pressure6[kPa]', 'Pressure7[kPa]', 'Pressure8[kPa]', 'FSR_L', 'FSR_R'])

    try:
        while True:
            # 시리얼 버퍼에 데이터가 있으면 읽기 시작
            if serialPort.in_waiting > 0:
                temp = serialPort.readline().decode('utf-8').strip()  # 시리얼 데이터 읽기
                temp = temp.replace('\0', '')  # Null 부분 삭제 
                print(f"Received line: {temp}")  # 디버그 용도

                # 빈 데이터가 아닌 경우만 처리
                if temp:
                    try:
                        # 데이터를 ','로 분리
                        data = temp.split(',')
                        
                        # 데이터가 올바르게 들어왔는지 확인
                        if len(data) >= 11:
                            # 'Time: '와 'Pressure: '를 분리하여 각각의 값 추출
                            time_data = float(data[0].strip())
                            pressure1_data = float(data[1].strip())
                            pressure2_data = float(data[2].strip())
                            pressure3_data = float(data[3].strip())
                            pressure4_data = float(data[4].strip())
                            pressure5_data = float(data[5].strip())
                            pressure6_data = float(data[6].strip())
                            pressure7_data = float(data[7].strip())
                            pressure8_data = float(data[8].strip())
                            FSR_L_data = float(data[9].strip())
                            FSR_R_data = float(data[10].strip())

                            # CSV 파일에 데이터 쓰기
                            writer.writerow([time_data, pressure1_data, pressure2_data, pressure3_data, pressure4_data, pressure5_data, pressure6_data, pressure7_data, pressure8_data, FSR_L_data, FSR_R_data])
                            
                        else:
                            print("Wrong data is received:", temp)
                    except IndexError:
                        print(f"IndexError: This data cannot be read. Received Data: {temp}")
                    except ValueError:
                        print(f"ValueError: This data cannot be converted. Received Data: {temp}")
                else:
                    print("Error: Received Empty data")

    except KeyboardInterrupt:
        print("Exit the program. Close the CSV file")
    
    except serial.SerialException as e:
        print(f"SerialException: {e}")
    
    finally:
        # 시리얼 포트와 파일 닫기
        serialPort.close()
        file.close()




# Plot the graph after data saving
data = pd.read_csv(csv_filename, header=0)

plt.figure(figsize=(10,6))
plt.plot(data['Time[ms]'], data['Pressure1[kPa]'], label='pMMG1', color='r')
plt.plot(data['Time[ms]'], data['Pressure2[kPa]'], label='pMMG2', color='orange')
plt.plot(data['Time[ms]'], data['Pressure3[kPa]'], label='pMMG3', color='yellow')
plt.plot(data['Time[ms]'], data['Pressure4[kPa]'], label='pMMG4', color='g')
plt.plot(data['Time[ms]'], data['Pressure5[kPa]'], label='pMMG5', color='b')
plt.plot(data['Time[ms]'], data['Pressure6[kPa]'], label='pMMG6', color='indigo')
plt.plot(data['Time[ms]'], data['Pressure7[kPa]'], label='pMMG7', color='violet')
plt.plot(data['Time[ms]'], data['Pressure8[kPa]'], label='pMMG8', color='brown')
plt.plot(data['Time[ms]'], data['FSR_L'], label='FSR_L', color='lightblue')
plt.plot(data['Time[ms]'], data['FSR_R'], label='FSR_R', color='lime')
plt.xlabel('Time[ms]', fontsize=15)
plt.ylabel('Pressure[kPa]', fontsize=15)
plt.title('Result of Experiment', fontsize=25)
plt.grid(alpha=0.4)
plt.legend(loc=1, fontsize=15)
plt.savefig('pMMG_result8.png')  
plt.show()


