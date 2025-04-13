from neo4j import GraphDatabase
import os
import json
from tqdm import tqdm

class MedicalGraph:
    def __init__(self):
        cur_dir = '/'.join(os.path.abspath(__file__).split('/')[:-1])
        self.data_path = os.path.join(cur_dir, 'data/medical.json')
        self.driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "**********"))

    def close(self):
        self.driver.close()

    '''读取文件'''
    def read_nodes(self):
        # 共７类节点
        # 药品
        drugs = []
        # 食物
        foods = []
        # 检查
        checks = []
        # 科室
        departments = []
        # 药品大类
        producers = []
        # 疾病
        diseases = []
        # 症状
        symptoms = []
        # 疾病信息
        disease_infos = []

        # 构建节点实体关系
        # 科室－科室关系
        rels_department = []
        # 疾病－忌吃食物关系
        rels_noteat = []
        # 疾病－宜吃食物关系
        rels_doeat = []
        # 疾病－推荐吃食物关系
        rels_recommandeat = []
        # 疾病－通用药品关系
        rels_commonddrug = []
        # 疾病－热门药品关系
        rels_recommanddrug = []
        # 疾病－检查关系
        rels_check = []
        # 厂商－药物关系
        rels_drug_producer = []

        # 疾病症状关系
        rels_symptom = []
        # 疾病并发关系
        rels_acompany = []
        # 疾病与科室之间的关系
        rels_category = []

        for data in tqdm(open(self.data_path, encoding="utf-8"), desc="Reading nodes", unit="node"):
            disease_dict = {}
            data_json = json.loads(data)
            disease = data_json['name']
            disease_dict['name'] = disease
            diseases.append(disease)
            disease_dict['desc'] = ''
            disease_dict['prevent'] = ''
            disease_dict['cause'] = ''
            disease_dict['easy_get'] = ''
            disease_dict['cure_department'] = ''
            disease_dict['cure_way'] = ''
            disease_dict['cure_lasttime'] = ''
            disease_dict['symptom'] = ''
            disease_dict['cured_prob'] = ''

            if 'symptom' in data_json:
                symptoms += data_json['symptom']
                for symptom in data_json['symptom']:
                    rels_symptom.append([disease, symptom])

            if 'acompany' in data_json:
                for acompany in data_json['acompany']:
                    rels_acompany.append([disease, acompany])

            if 'desc' in data_json:
                disease_dict['desc'] = data_json['desc']

            if 'prevent' in data_json:
                disease_dict['prevent'] = data_json['prevent']

            if 'cause' in data_json:
                disease_dict['cause'] = data_json['cause']

            if 'get_prob' in data_json:
                disease_dict['get_prob'] = data_json['get_prob']

            if 'easy_get' in data_json:
                disease_dict['easy_get'] = data_json['easy_get']

            if 'cure_department' in data_json:
                cure_department = data_json['cure_department']
                if len(cure_department) == 1:
                    rels_category.append([disease, cure_department[0]])
                if len(cure_department) == 2:
                    big = cure_department[0]
                    small = cure_department[1]
                    rels_department.append([small, big])
                    rels_category.append([disease, small])

                disease_dict['cure_department'] = cure_department
                departments += cure_department

            if 'cure_way' in data_json:
                disease_dict['cure_way'] = data_json['cure_way']

            if  'cure_lasttime' in data_json:
                disease_dict['cure_lasttime'] = data_json['cure_lasttime']

            if 'cured_prob' in data_json:
                disease_dict['cured_prob'] = data_json['cured_prob']

            if 'common_drug' in data_json:
                common_drug = data_json['common_drug']
                for drug in common_drug:
                    rels_commonddrug.append([disease, drug])
                drugs += common_drug

            if 'recommand_drug' in data_json:
                recommand_drug = data_json['recommand_drug']
                drugs += recommand_drug
                for drug in recommand_drug:
                    rels_recommanddrug.append([disease, drug])

            if 'not_eat' in data_json:
                not_eat = data_json['not_eat']
                for _not in not_eat:
                    rels_noteat.append([disease, _not])

                foods += not_eat
                do_eat = data_json['do_eat']
                for _do in do_eat:
                    rels_doeat.append([disease, _do])

                foods += do_eat
                recommand_eat = data_json['recommand_eat']

                for _recommand in recommand_eat:
                    rels_recommandeat.append([disease, _recommand])
                foods += recommand_eat

            if 'check' in data_json:
                check = data_json['check']
                for _check in check:
                    rels_check.append([disease, _check])
                checks += check
            if 'drug_detail' in data_json:
                drug_detail = data_json['drug_detail']
                producer = [i.split('(')[0] for i in drug_detail]
                rels_drug_producer += [[i.split('(')[0], i.split('(')[-1].replace(')', '')] for i in drug_detail]
                producers += producer
            disease_infos.append(disease_dict)
        return set(drugs), set(foods), set(checks), set(departments), set(producers), set(symptoms), set(diseases), disease_infos,\
               rels_check, rels_recommandeat, rels_noteat, rels_doeat, rels_department, rels_commonddrug, rels_drug_producer, rels_recommanddrug,\
               rels_symptom, rels_acompany, rels_category

    '''建立节点'''
    def create_node(self, label, nodes):
        with self.driver.session() as session:
            # 使用 tqdm 包装 nodes 以显示进度条
            for node_name in tqdm(nodes, desc=f"Creating {label} nodes", unit="node"):
                query = f"CREATE (n:{label} {{name: $name}})"
                params = {'name': node_name}
                try:
                    session.run(query, params)
                except Exception as e:
                    print(f"Error: {e}")
        return

    '''创建知识图谱中心疾病的节点'''
    def create_diseases_nodes(self, disease_infos):
        with self.driver.session() as session:
            for disease_dict in tqdm(disease_infos, desc=f"Creating diseases nodes", unit="node"):
                query = """
                CREATE (d:Disease {name: $name, desc: $desc, prevent: $prevent, cause: $cause, easy_get: $easy_get,
                                    cure_lasttime: $cure_lasttime, cure_department: $cure_department,
                                    cure_way: $cure_way, cured_prob: $cured_prob})
                """
                params = {
                    'name': disease_dict['name'],
                    'desc': disease_dict['desc'],
                    'prevent': disease_dict['prevent'],
                    'cause': disease_dict['cause'],
                    'easy_get': disease_dict['easy_get'],
                    'cure_lasttime': disease_dict['cure_lasttime'],
                    'cure_department': disease_dict['cure_department'],
                    'cure_way': disease_dict['cure_way'],
                    'cured_prob': disease_dict['cured_prob']
                }
                try:
                    session.run(query, params)
                except Exception as e:
                    print(f"Error: {e}")

    '''创建知识图谱实体节点类型schema'''

    def create_graphnodes(self):
        Drugs, Foods, Checks, Departments, Producers, Symptoms, Diseases, disease_infos, \
            rels_check, rels_recommandeat, rels_noteat, rels_doeat, rels_department, \
            rels_commonddrug, rels_drug_producer, rels_recommanddrug, rels_symptom, \
            rels_acompany, rels_category = self.read_nodes()

        self.create_diseases_nodes(disease_infos)
        self.create_node('Drug', Drugs)
        self.create_node('Food', Foods)
        self.create_node('Check', Checks)
        self.create_node('Department', Departments)
        self.create_node('Producer', Producers)
        self.create_node('Symptom', Symptoms)


    '''创建实体关系边'''
    def create_graphrels(self):
        Drugs, Foods, Checks, Departments, Producers, Symptoms, Diseases, disease_infos, \
        rels_check, rels_recommandeat, rels_noteat, rels_doeat, rels_department, \
        rels_commonddrug, rels_drug_producer, rels_recommanddrug, rels_symptom, \
        rels_acompany, rels_category = self.read_nodes()

        self.create_relationship('Disease', 'Food', rels_recommandeat, 'recommand_eat', '推荐食谱')
        self.create_relationship('Disease', 'Food', rels_noteat, 'no_eat', '忌吃')
        self.create_relationship('Disease', 'Food', rels_doeat, 'do_eat', '宜吃')
        self.create_relationship('Department', 'Department', rels_department, 'belongs_to', '属于')
        self.create_relationship('Disease', 'Drug', rels_commonddrug, 'common_drug', '常用药品')
        self.create_relationship('Producer', 'Drug', rels_drug_producer, 'drugs_of', '生产药品')
        self.create_relationship('Disease', 'Drug', rels_recommanddrug, 'recommand_drug', '好评药品')
        self.create_relationship('Disease', 'Check', rels_check, 'need_check', '诊断检查')
        self.create_relationship('Disease', 'Symptom', rels_symptom, 'has_symptom', '症状')
        self.create_relationship('Disease', 'Disease', rels_acompany, 'acompany_with', '并发症')
        self.create_relationship('Disease', 'Department', rels_category, 'belongs_to', '所属科室')


    '''创建实体关联边'''
    def create_relationship(self, start_node, end_node, edges, rel_type, rel_name):
        # 去重处理
        set_edges = []
        for edge in edges:
            set_edges.append('###'.join(edge))
        all = len(set(set_edges))
        with self.driver.session() as session:  # 使用 session 来执行查询
            for edge in tqdm(set(set_edges), desc=f"Creating {rel_type} edges", unit="edge"):
                edge = edge.split('###')
                p = edge[0]
                q = edge[1]

                # 使用参数化查询来避免特殊字符问题
                query = f"""
                MATCH (p:{start_node}), (q:{end_node})
                WHERE p.name = $p_name AND q.name = $q_name
                CREATE (p)-[rel:{rel_type} {{name: $rel_name}}]->(q)
                """

                params = {
                    'p_name': p,
                    'q_name': q.replace('（', '(').replace('）', ')'),  # 替换中文括号
                    'rel_name': rel_name
                }

                try:
                    session.run(query, params)
                except Exception as e:
                    print(f"Error creating relationship: {e}")
        return

    '''导出数据'''
    def export_data(self):
        Drugs, Foods, Checks, Departments, Producers, Symptoms, Diseases, disease_infos, \
        rels_check, rels_recommandeat, rels_noteat, rels_doeat, rels_department, \
        rels_commonddrug, rels_drug_producer, rels_recommanddrug, rels_symptom, \
        rels_acompany, rels_category = self.read_nodes()

        with open('drug.txt', 'w+') as f_drug, \
             open('food.txt', 'w+') as f_food, \
             open('check.txt', 'w+') as f_check, \
             open('department.txt', 'w+') as f_department, \
             open('producer.txt', 'w+') as f_producer, \
             open('symptoms.txt', 'w+') as f_symptom, \
             open('disease.txt', 'w+') as f_disease:
            f_drug.write('\n'.join(list(Drugs)))
            f_food.write('\n'.join(list(Foods)))
            f_check.write('\n'.join(list(Checks)))
            f_department.write('\n'.join(list(Departments)))
            f_producer.write('\n'.join(list(Producers)))
            f_symptom.write('\n'.join(list(Symptoms)))
            f_disease.write('\n'.join(list(Diseases)))

if __name__ == '__main__':
    handler = MedicalGraph()
    handler.export_data()
    handler.create_graphnodes()
    handler.create_graphrels()
