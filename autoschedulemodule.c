#include <Python.h>
#include <stdint.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>



typedef struct {
    uint32_t day_bits[6]; 
    int id;              
} Schedule; 

typedef struct {
    Schedule *schedules;
    int count;          
} ScheduleSet; 

typedef struct {
    Schedule schedule;
    int total_penalty;
    int *ids; 
} ScoredSchedule; 

typedef struct PQNode {
    ScoredSchedule *data;
    struct PQNode *next;
} PQNode;

typedef struct {
    PQNode *head;
    int size;
    int capacity;
} PriorityQueue;





int has_conflict(const Schedule *a, 
                const Schedule *b);

void combine_schedules(Schedule *result,   
                    const Schedule *a, 
                    const Schedule *b);

int count_gaps(const Schedule *schedule);

int count_conflicts(const Schedule *schedule, 
                    const Schedule *leisure_time);

void copy_schedule(Schedule *dest, const Schedule *src);

void select_schedules(int set_index, 
                    int total_sets, 
                    ScheduleSet *sets,
                    Schedule *current_combined, 
                    int current_penalty,
                    int *current_ids, 
                    Schedule *leisure_time,
                    PriorityQueue *top_schedules, 
                    int gap_penalty,
                    int conflict_penalty);
                      
PriorityQueue *create_priority_queue(int capacity);

void free_priority_queue(PriorityQueue *pq);
int is_priority_queue_empty(PriorityQueue *pq);

void insert_into_priority_queue(PriorityQueue *pq, 
                                ScoredSchedule *scored_schedule);

ScoredSchedule *extract_min(PriorityQueue *pq);

int should_prune(int total_penalty, 
                PriorityQueue *pq);

int calculate_penalty(const Schedule *combined, 
                    const Schedule *candidate,
                    const Schedule *leisure_time, 
                    int gap_penalty, 
                    int conflict_penalty);







int has_conflict(const Schedule *a, const Schedule *b) {
    for (int i = 0; i < 6; i++) {
        if (a->day_bits[i] & b->day_bits[i]) {
            return 1; 
        }
    }
    return 0; 
}


void combine_schedules(Schedule *result, const Schedule *a, const Schedule *b) {
    for (int i = 0; i < 6; i++) {
        result->day_bits[i] = a->day_bits[i] | b->day_bits[i];
    }
}


int count_gaps(const Schedule *schedule) {
    int total_gaps = 0;
    for (int i = 0; i < 6; i++) {
        uint32_t day = schedule->day_bits[i];
        int gaps = 0;
        int in_slot = 0;
        for (int j = 0; j < 32; j++) {
            int bit = (day >> j) & 1U;
            if (bit) {
                if (!in_slot) {
                    in_slot = 1;
                }
            } else {
                if (in_slot) {
                    in_slot = 0;
                    gaps++;
                }
            }
        }
        total_gaps += gaps;
    }
    return total_gaps;
}


int count_conflicts(const Schedule *schedule, const Schedule *leisure_time) {
    int conflicts = 0;
    for (int i = 0; i < 6; i++) {
        uint32_t overlap = schedule->day_bits[i] & leisure_time->day_bits[i];

        while (overlap) {
            conflicts += overlap & 1U;
            overlap >>= 1;
        }
    }
    return conflicts;
}


void copy_schedule(Schedule *dest, const Schedule *src) {
    memcpy(dest->day_bits, src->day_bits, sizeof(uint32_t) * 6);
    dest->id = src->id;
}


void select_schedules(int set_index, int total_sets, ScheduleSet *sets,
                      Schedule *current_combined, int current_penalty,
                      int *current_ids, Schedule *leisure_time,
                      PriorityQueue *top_schedules, int gap_penalty,
                      int conflict_penalty) {
    if (set_index == total_sets) {


        int gaps = count_gaps(current_combined);
        int total_penalty = current_penalty + (gaps * gap_penalty);

        ScoredSchedule *scored_schedule = (ScoredSchedule *)malloc(sizeof(ScoredSchedule));
        copy_schedule(&scored_schedule->schedule, current_combined);
        scored_schedule->total_penalty = total_penalty;
        scored_schedule->ids = (int *)malloc(sizeof(int) * total_sets);
        memcpy(scored_schedule->ids, current_ids, sizeof(int) * total_sets);

        insert_into_priority_queue(top_schedules, scored_schedule);

        return;
    }

    ScheduleSet *current_set = &sets[set_index];
    for (int i = 0; i < current_set->count; i++) {
        Schedule *candidate = &current_set->schedules[i];
        if (!has_conflict(current_combined, candidate)) {
            Schedule new_combined;
            combine_schedules(&new_combined, current_combined, candidate);
            current_ids[set_index] = candidate->id;

            int conflicts = count_conflicts(candidate, leisure_time);
            int penalty = conflicts * conflict_penalty;

            int estimated_penalty = current_penalty + penalty;

            if (should_prune(estimated_penalty, top_schedules)) {
                continue;
            }

            select_schedules(set_index + 1, total_sets, sets, &new_combined,
                             estimated_penalty, current_ids, leisure_time,
                             top_schedules, gap_penalty, conflict_penalty);
        }
    }
}


void free_schedule_sets(int total_sets, ScheduleSet *sets) {
    for (int i = 0; i < total_sets; i++) {
        free(sets[i].schedules);
    }
    free(sets);
}


PriorityQueue *create_priority_queue(int capacity) {
    PriorityQueue *pq = (PriorityQueue *)malloc(sizeof(PriorityQueue));
    pq->head = NULL;
    pq->size = 0;
    pq->capacity = capacity;
    return pq;
}


void free_priority_queue(PriorityQueue *pq) {
    PQNode *current = pq->head;
    while (current) {
        PQNode *next = current->next;
        free(current->data->ids);
        free(current->data);
        free(current);
        current = next;
    }
    free(pq);
}


int is_priority_queue_empty(PriorityQueue *pq) {
    return pq->size == 0;
}


void insert_into_priority_queue(PriorityQueue *pq, ScoredSchedule *scored_schedule) {
    PQNode *new_node = (PQNode *)malloc(sizeof(PQNode));
    new_node->data = scored_schedule;
    new_node->next = NULL;

    if (!pq->head || scored_schedule->total_penalty < pq->head->data->total_penalty) {
        new_node->next = pq->head;
        pq->head = new_node;
    } else {
        PQNode *current = pq->head;
        while (current->next && current->next->data->total_penalty <= scored_schedule->total_penalty) {
            current = current->next;
        }
        new_node->next = current->next;
        current->next = new_node;
    }

    pq->size++;
    if (pq->size > pq->capacity) {
        PQNode *current = pq->head;
        while (current->next && current->next->next) {
            current = current->next;
        }
        PQNode *to_remove = current->next;
        current->next = NULL;
        free(to_remove->data->ids);
        free(to_remove->data);
        free(to_remove);
        pq->size--;
    }
}


ScoredSchedule *extract_min(PriorityQueue *pq) {
    if (is_priority_queue_empty(pq)) {
        return NULL;
    }
    PQNode *node = pq->head;
    pq->head = node->next;
    ScoredSchedule *data = node->data;
    free(node);
    pq->size--;
    return data;
}


int should_prune(int total_penalty, PriorityQueue *pq) {
    if (pq->size < pq->capacity) {
        return 0;
    }

    PQNode *current = pq->head;
    while (current->next) {
        current = current->next;
    }
    if (total_penalty >= current->data->total_penalty) {
        return 1;
    }
    return 0;
}


static PyObject *py_get_best_schedules(PyObject *self, PyObject *args) {
    int total_sets;
    PyObject *py_sets;
    PyObject *py_leisure_time;
    int gap_penalty = 1;
    int conflict_penalty = 10;
    int top_n = 5;

    if (!PyArg_ParseTuple(args, "iOO|iii", &total_sets, &py_sets, &py_leisure_time,
                          &gap_penalty, &conflict_penalty, &top_n)) {
        return NULL;
    }

    ScheduleSet *sets = (ScheduleSet *)malloc(sizeof(ScheduleSet) * total_sets);

    for (int i = 0; i < total_sets; i++) {
        PyObject *set_obj = PyList_GetItem(py_sets, i);
        int count = (int)PyList_Size(set_obj);

        sets[i].count = count;
        sets[i].schedules = (Schedule *)malloc(sizeof(Schedule) * count);

        for (int j = 0; j < count; j++) {
            PyObject *sched_obj = PyList_GetItem(set_obj, j);
            Schedule *sched = &sets[i].schedules[j];

            for (int k = 0; k < 6; k++) {
                sched->day_bits[k] = (uint32_t)PyLong_AsUnsignedLong(PyList_GetItem(sched_obj, k));
            }
            sched->id = (int)PyLong_AsLong(PyList_GetItem(sched_obj, 6)); 
        }
    }

    Schedule leisure_time;
    for (int k = 0; k < 6; k++) {
        leisure_time.day_bits[k] = (uint32_t)PyLong_AsUnsignedLong(PyList_GetItem(py_leisure_time, k));
    }
    leisure_time.id = -1; 

    PriorityQueue *top_schedules = create_priority_queue(top_n);

    int *current_ids = (int *)malloc(sizeof(int) * total_sets);

    Schedule current_combined = {0};

    select_schedules(0, total_sets, sets, &current_combined, 0,
                     current_ids, &leisure_time, top_schedules, gap_penalty, conflict_penalty);

    PyObject *result_list = PyList_New(0);

    while (!is_priority_queue_empty(top_schedules)) {
        ScoredSchedule *scored_schedule = extract_min(top_schedules);

        PyObject *ids_list = PyList_New(total_sets);
        for (int i = 0; i < total_sets; i++) {
            PyList_SetItem(ids_list, i, PyLong_FromLong(scored_schedule->ids[i]));
        }

        PyObject *schedule_info = PyDict_New();
        PyDict_SetItemString(schedule_info, "ids", ids_list);
        PyDict_SetItemString(schedule_info, "penalty", PyLong_FromLong(scored_schedule->total_penalty));

        PyList_Append(result_list, schedule_info);

        free(scored_schedule->ids);
        free(scored_schedule);
    }

    free_priority_queue(top_schedules);
    free(current_ids);
    free_schedule_sets(total_sets, sets);

    return result_list;
}


static PyMethodDef SchedulingMethods[] = {
    {"get_best_schedules", py_get_best_schedules, METH_VARARGS,
     "Yam yam."},
    {NULL, NULL, 0, NULL}
};


static struct PyModuleDef schedulingmodule = {
    PyModuleDef_HEAD_INIT,
    "schedulingmodule",
    NULL,
    -1,
    SchedulingMethods
};


PyMODINIT_FUNC PyInit_schedulingmodule(void) {
    return PyModule_Create(&schedulingmodule);
}
