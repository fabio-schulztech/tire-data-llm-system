"""
Módulo para simulação de desgaste e custos de pneus.

Este módulo contém funções para calcular o impacto de subpressão e temperatura
na vida útil dos pneus, no consumo de combustível e nas emissões de CO₂. Os
parâmetros foram definidos com base nas constantes fornecidas pelo usuário.

Todas as funções retornam dados estruturados em vez de imprimir na tela,
permitindo fácil integração com APIs e interfaces web.
"""

from dataclasses import dataclass

# Constantes de configuração (podem ser ajustadas conforme necessidade)
tire_cost = 2450.0  # Custo de um pneu em R$
fuel_cost_per_liter = 6.02  # Custo do combustível por litro em R$
fuel_efficiency_km_per_liter = 1.51  # Eficiência média de combustível em km/l
subpressure_min = 5.0  # Subpressão mínima considerada (%)
subpressure_max = 10.0  # Subpressão máxima considerada (%)
tpms_cost_per_tire = 20.0  # Custo do sensor TPMS por pneu em R$
num_vehicles = 1  # Número de veículos
tire_life_km = 200000.0  # Vida útil nominal do pneu (km) ajustada para 200k
ideal_pressure = 120.0  # Pressão ideal do pneu (PSI)
pressao_alerta = ideal_pressure * 0.8  # Pressão de alerta (80% da ideal)
temperatura_alerta = 80.0  # Temperatura de alerta (°C)


def fator_consumo_temperatura(temp: float) -> float:
    """Retorna o fator de aumento de consumo de combustível de acordo com a temperatura."""
    if temp <= 65:
        return 0.0
    elif temp <= 75:
        return 0.015
    elif temp <= 85:
        return 0.03
    else:
        return 0.05


def fator_desgaste_temperatura(temp: float) -> float:
    """Retorna o fator de desgaste do pneu de acordo com a temperatura."""
    if temp <= 65:
        return 1.0
    elif temp <= 75:
        return 1.3
    elif temp <= 85:
        return 1.7
    else:
        return 2.2


def process_reading(pressure: float, temperature: float, distance: float) -> dict:
    """
    Calcula métricas de desgaste e custo para uma leitura de TPMS.

    Args:
        pressure (float): Pressão do pneu em PSI
        temperature (float): Temperatura do pneu em °C
        distance (float): Distância percorrida em km durante o intervalo considerado

    Returns:
        dict: Dicionário contendo várias métricas de desgaste, consumo e custo.
    """
    # Subcalibragem percentual
    subpressure_percentage = max(0.0, (ideal_pressure - pressure) / ideal_pressure * 100.0)

    # Consumo de combustível no intervalo (litros)
    fuel_used = distance / fuel_efficiency_km_per_liter

    # Fatores de temperatura
    desgaste_temp = fator_desgaste_temperatura(temperature)
    consumo_temp = fator_consumo_temperatura(temperature)

    # Fatores de pressão
    desgaste_pressao = 1.0
    consumo_pressao = 0.0
    if subpressure_percentage > 40:
        desgaste_pressao = 1.8
        consumo_pressao = 0.06
    elif subpressure_percentage > 20:
        desgaste_pressao = 1.6
        consumo_pressao = 0.04
    elif subpressure_percentage > 10:
        desgaste_pressao = 1.3
        consumo_pressao = 0.02
    elif subpressure_percentage > 5:
        desgaste_pressao = 1.1
        consumo_pressao = 0.01

    # Combinação de fatores
    fator_desgaste_total = desgaste_temp * desgaste_pressao
    fator_consumo_total = consumo_temp + consumo_pressao

    # Desgaste do pneu em km e custo correspondente
    tire_life_loss_km = distance * fator_desgaste_total
    custo_pneu_km = (tire_cost / tire_life_km) * tire_life_loss_km
    tire_life_remaining_km = max(tire_life_km - tire_life_loss_km, 0.0)

    # Desperdício de combustível (litros) e custo extra
    fuel_waste = fuel_used * fator_consumo_total
    custo_extra_combustivel_km = fuel_waste * fuel_cost_per_liter

    # Emissões de CO₂ e benefícios ESG
    co2_emission_factor = 2.68  # kg de CO₂ por litro de diesel
    co2_reduction = fuel_waste * co2_emission_factor
    carbon_price_min = 0.05  # R$ por kg de CO₂
    carbon_price_max = 0.15
    financial_savings_min = co2_reduction * carbon_price_min
    financial_savings_max = co2_reduction * carbon_price_max

    # Score de risco operacional (escala arbitrária)
    risco_score = round((fator_desgaste_total * 2 + fator_consumo_total * 100), 2)

    return {
        "pressure": pressure,
        "temperature": temperature,
        "distance": distance,
        "subpressure_percentage": round(subpressure_percentage, 2),
        "fator_desgaste_total": round(fator_desgaste_total, 3),
        "fator_consumo_total": round(fator_consumo_total, 3),
        "tire_life_loss_km": round(tire_life_loss_km, 2),
        "tire_life_remaining_km": round(tire_life_remaining_km, 2),
        "custo_pneu_km": round(custo_pneu_km, 4),
        "fuel_waste": round(fuel_waste, 2),
        "custo_extra_combustivel_km": round(custo_extra_combustivel_km, 4),
        "custo_total_km": round(custo_pneu_km + custo_extra_combustivel_km, 4),
        "co2_reduction": round(co2_reduction, 2),
        "financial_savings_min": round(financial_savings_min, 2),
        "financial_savings_max": round(financial_savings_max, 2),
        "risco_score": risco_score
    }